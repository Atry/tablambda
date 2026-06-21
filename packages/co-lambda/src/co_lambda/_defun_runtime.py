"""The defunctionalized runtime: the minimal execution substrate for compiled code.

Generated code references exactly two free names from this module: ``Thunk`` and ``interned``.
Everything else is internal implementation (``_BOTTOM``, ``fixpoint_cached_property``) or a
host import (``dataclass``). The runtime holds NO domain logic; all compilation decisions live
in the pure-lambda compiler ``_defun_codegen``.
"""

from __future__ import annotations

import hashlib
import struct
import sys
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, fields as dataclass_fields
from enum import Enum, auto
from typing import Any, Literal, Protocol, TypeGuard, Union, TypeVar, overload

from typing_extensions import dataclass_transform

from fixpoints._core import fixpoint_cached_property, fixpoint_slotted

_T = TypeVar("_T")


class _DefunBottom(Enum):
    BOTTOM = auto()


_BOTTOM = _DefunBottom.BOTTOM


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
    """Class decorator: make ``cls`` a frozen-by-identity dataclass and hash-cons its instances.

    Applies ``dataclass(eq=False, slots=slots)`` internally (so generated code needs only
    ``@interned``, not a separate ``@dataclass``), then interns. ``slots=True`` (the default) makes the
    closures the compiler emits slotted, which is faster and lighter; ``eq=False`` keeps identity-based
    equality. Usable bare (``@interned``) or parameterised (``@interned(slots=False)``).
    """
    if cls is None:
        return lambda klass: interned(klass, slots=slots)
    cls = dataclass(eq=False, slots=slots)(cls)
    field_names = tuple(f.name for f in dataclass_fields(cls))
    return _intern(cls, field_names)


def _deterministic_hash(*parts: int) -> int:
    """A deterministic hash from a sequence of integers, independent of ``PYTHONHASHSEED``."""
    data = struct.pack(f">{len(parts)}q", *parts)
    return int.from_bytes(hashlib.sha256(data).digest()[:8], "big")


@fixpoint_slotted
class Thunk:
    """A suspended application (redex). Interned so structurally equal redexes share identity,
    enabling tabling: ``weak_head_normal_form`` is computed once per distinct ``Thunk``.

    Slotted for speed and low memory; ``@fixpoint_slotted`` automatically adds a dedicated cache
    slot for each ``fixpoint_cached_property``, avoiding a ``__dict__`` or intermediate dict.
    Identity-based equality (``object.__eq__``).
    """

    __slots__ = ("callee", "argument")

    def __init__(self, callee: Lambda, argument: Lambda) -> None:
        self.callee = callee
        self.argument = argument

    def __call__(self, a: Lambda) -> Thunk:
        return Thunk(self, a)

    @fixpoint_cached_property(bottom=lambda: _BOTTOM)
    def weak_head_normal_form(self) -> Lambda | Literal[_DefunBottom.BOTTOM]:
        callee = self.callee
        if _is_thunk(callee):
            callee = callee.weak_head_normal_form
            if callee is _BOTTOM:
                return _BOTTOM
        result = callee(self.argument)
        return result.weak_head_normal_form if _is_thunk(result) else result


Thunk = _intern(Thunk, ("callee", "argument"))


def _is_thunk(x: object) -> TypeGuard[Thunk]:
    return isinstance(x, Thunk)


class Lambda(Protocol):
    """A lambda value: any callable that takes a Lambda and returns a Lambda or Thunk."""

    def __call__(self, a: Lambda) -> Union["Lambda", "Thunk"]: ...


# --- stack helpers ---------------------------------------------------------------------------------

_COMPILE_RECURSION_LIMIT = 16_000
_RECURSION_LIMIT = 200_000
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
