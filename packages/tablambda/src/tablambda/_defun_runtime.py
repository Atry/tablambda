"""The defunctionalized runtime: the minimal execution substrate for compiled code.

Generated code references three free names from this module: ``Closure``, ``Thunk``, and ``interned``.
A compiled ``Closure`` and a ``Thunk`` are both ``Node``s, so they share the interpreter's
``weak_head_normal_form`` and interning and can run mixed with interpreted terms. The runtime holds NO
domain logic; all compilation decisions live in the pure-lambda compiler ``_defun_codegen``.
"""

from __future__ import annotations

import hashlib
import struct
import sys
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, fields as dataclass_fields
from typing import Any, TypeGuard, TypeVar, overload

from typing_extensions import dataclass_transform

from tablambda._ast import Node, WeakHeadBottom

_T = TypeVar("_T")

# The compiled runtime shares the interpreter's single bottom (``WeakHeadBottom``); ``_BOTTOM`` is the
# terse internal alias used at the forcing call sites.
_BOTTOM = WeakHeadBottom.BOTTOM


class Closure(Node, ABC):
    """A compiled closure: an opaque, closed, 1-ary callable ``Node`` (the defunctionalized value, and
    the FFI). Every closure class the compiler emits subclasses ``Closure`` (injected by ``interned``),
    so a compiled value is a ``Node`` and shares the interpreter's ``weak_head_normal_form`` and
    interning. A closure is a weak-head value (its weak head normal form is itself), and it is closed,
    so its ``loose_bound`` is ``0`` and ``shift``/``substitute`` leave it untouched.
    """

    __slots__ = ()

    # Closures are closed: no exposed de Bruijn index, so shift/substitute are identity.
    loose_bound = 0

    @abstractmethod
    def __call__(self, argument: Node) -> Node: ...


def _intern(cls: type[_T], field_names: tuple[str, ...]) -> type[_T]:
    """Hash-cons ``cls``'s instances by ``(cls, field-values-by-identity)``.

    Two instances of the same class with identical field values (by ``is``) become the same object.
    Fields are themselves interned closures or ``Thunk`` instances, so identity comparison is O(1)
    structural equality, matching ``_ast._intern_node``. The hash-cons table is exposed as
    ``__intern_pool__`` for introspection (e.g. counting tabled objects in a benchmark); it is the SAME
    table the interner already keeps, so surfacing it adds no behaviour.

    The key is computed directly from the positional constructor arguments (which correspond 1:1 to
    ``field_names`` for both ``@dataclass`` classes and ``Thunk``), so a cache hit avoids allocating
    a throwaway instance entirely.
    """
    pool: dict[tuple, object] = {}
    original_init = cls.__init__

    def __new__(klass, *args):
        key = (klass,) + tuple(id(a) for a in args)
        existing = pool.get(key)
        if existing is not None:
            return existing
        instance = object.__new__(klass)
        original_init(instance, *args)
        pool[key] = instance
        return instance

    cls_any: Any = cls
    cls_any.__new__ = __new__
    cls_any.__init__ = lambda self, *args, **kwargs: None
    cls_any.__intern_pool__ = pool
    return cls


@overload
def interned(cls: type[_T], *, slots: bool = ...) -> type[_T]: ...


@overload
def interned(
    cls: None = ..., *, slots: bool = ...
) -> Callable[[type[_T]], type[_T]]: ...


@dataclass_transform(eq_default=False)
def interned(cls=None, *, slots=True):
    """Class decorator: make a generated ``Closure`` subclass a frozen-by-identity dataclass and
    hash-cons its instances.

    Applies ``dataclass(eq=False, slots=slots)`` internally (so generated code needs only
    ``@interned``, not a separate ``@dataclass``), then interns. ``slots=True`` (the default) makes the
    closures the compiler emits slotted, which is faster and lighter; ``eq=False`` keeps identity-based
    equality. The compiler emits each closure as ``@interned class vg_...(Closure)``, so the class is
    already a ``Node`` before this decorator runs. Usable bare (``@interned``) or parameterised
    (``@interned(slots=False)``).
    """
    if cls is None:
        return lambda klass: interned(klass, slots=slots)
    assert issubclass(cls, Closure), f"@interned expects a Closure subclass, got {cls!r}"
    cls = dataclass(eq=False, slots=slots)(cls)
    field_names = tuple(f.name for f in dataclass_fields(cls))
    return _intern(cls, field_names)


def _deterministic_hash(*parts: int) -> int:
    """A deterministic hash from a sequence of integers, independent of ``PYTHONHASHSEED``."""
    data = struct.pack(f">{len(parts)}q", *parts)
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big")


class Thunk(Node):
    """A suspended application (redex) as a ``Node``: an ``App`` whose callee is a compiled value.
    Interned so structurally equal redexes share identity, enabling tabling: its
    ``weak_head_normal_form`` (inherited from ``Node``) is computed once per distinct ``Thunk``.

    It does NOT redeclare ``weak_head_normal_form`` (that would duplicate ``Node``'s fixpoint cache
    slot); instead ``_shape.compute_weak_head_normal_form`` dispatches a ``Thunk`` to ``force``.
    A thunk is closed, so its ``loose_bound`` is ``0``.
    """

    __slots__ = ("callee", "argument")

    # A redex over closed compiled values is itself closed.
    loose_bound = 0

    def __init__(self, callee: Node, argument: Node) -> None:
        self.callee = callee
        self.argument = argument

    def __call__(self, a: Node) -> "Thunk":
        return Thunk(self, a)

    def force(self) -> Node | WeakHeadBottom:
        """The weak head normal form of this redex: force the callee to a value, apply it to the
        argument, and force the result. Mixed-safe: the callee may force to an interpreter ``Lam`` or a
        ``Closure``, and ``apply_value`` handles both."""
        from tablambda._shape import apply_value, weak_head_normalize

        callee = weak_head_normalize(self.callee)
        if callee is _BOTTOM:
            return _BOTTOM
        result = apply_value(callee, self.argument)
        if result is _BOTTOM:
            return _BOTTOM
        return weak_head_normalize(result)


Thunk = _intern(Thunk, ("callee", "argument"))


def _is_thunk(x: object) -> TypeGuard[Thunk]:
    return isinstance(x, Thunk)


# --- stack helpers ---------------------------------------------------------------------------------

_COMPILE_RECURSION_LIMIT = 16_000
_RECURSION_LIMIT = 2_000_000
_STACK_SIZE = 1024 * 1024 * 1024  # 1 GiB


@contextmanager
def recursion_headroom() -> Iterator[None]:
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous, _COMPILE_RECURSION_LIMIT))
    try:
        yield
    finally:
        sys.setrecursionlimit(previous)


def _python_tag() -> str:
    """A Python-version tag for generated-module filenames, e.g. ``py313``. Defunctionalized modules
    are rendered with ``ast.unparse``, whose formatting can differ between Python versions, so a module
    generated under one interpreter must not be reused under another; the tag keeps artifacts distinct.
    """
    return f"py{sys.version_info.major}{sys.version_info.minor}"


def run_in_large_stack(thunk):
    """Run ``thunk`` in a thread with a 1 GiB C stack and a high recursion limit."""
    result: list = []

    def run() -> None:
        previous_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(previous_limit, _RECURSION_LIMIT))
        try:
            result.append(thunk())
        finally:
            sys.setrecursionlimit(previous_limit)

    previous_stack_size = threading.stack_size(_STACK_SIZE)
    try:
        worker = threading.Thread(target=run)
        worker.start()
        worker.join()
    finally:
        threading.stack_size(previous_stack_size)
    (single_result,) = result
    return single_result
