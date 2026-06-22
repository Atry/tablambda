"""Least-fixpoint cached-property infrastructure for mutual recursion.

``fixpoint_cached_property`` and ``fixpoint_dependent`` are drop-in
replacements for ``functools.cached_property`` that resolve mutually
recursive computations by least-fixpoint iteration.  When reentry (a cycle)
is detected, the outermost caller drives a digest loop that re-evaluates
participants until their values stabilize, starting from a configurable
bottom value.
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from contextvars import ContextVar
from enum import Enum
from functools import cached_property
from typing import Callable, ClassVar


class _FixpointContext:
    """Tracks the state of a fixpoint iteration (digest cycle).

    Stored in a ContextVar so that nested/concurrent fixpoint computations
    are isolated per-thread/per-coroutine.
    """

    __slots__ = ("computing", "reentrant", "participant_ids", "participant_refs",
                 "_clearable_attr_names", "approximations")

    def __init__(self, clearable_attr_names: frozenset[str]) -> None:
        self.computing: set[tuple[int, str]] = set()
        self.reentrant: bool = False
        self.participant_ids: set[int] = set()
        self.participant_refs: list[object] = []
        self._clearable_attr_names = clearable_attr_names
        self.approximations: dict[tuple[int, str], object] = {}

    def add_participant(self, instance: object) -> None:
        instance_id = id(instance)
        if instance_id not in self.participant_ids:
            self.participant_ids.add(instance_id)
            self.participant_refs.append(instance)

    def clear_participant_caches(self) -> None:
        """Clear all fixpoint-related cached values on all participants.

        Before clearing, save each value into ``approximations`` so that
        intermediate fixpoint_cached_property computations can use their
        previous iteration's result as an approximation instead of bottom
        when they encounter reentry.
        """
        for instance in self.participant_refs:
            instance_id = id(instance)
            for attr_name in self._clearable_attr_names:
                value = _clear_fixpoint_attr(instance, attr_name)
                if value is not None:
                    self.approximations[(instance_id, attr_name)] = value


_fixpoint_context_var: ContextVar[_FixpointContext | None] = ContextVar(
    "_fixpoint_context_var", default=None
)


class FixpointRecursionError(RecursionError):
    """Raised when fixpoint iteration is exhausted or reentry is detected with no iterations remaining.

    Carries the best approximation computed so far in ``incomplete_result``.
    As a ``RecursionError`` subclass, existing code that catches ``RecursionError``
    will also catch ``FixpointRecursionError``.
    """

    incomplete_result: object

    def __init__(self, message: str, *, incomplete_result: object) -> None:
        super().__init__(message)
        self.incomplete_result = incomplete_result


_FIXPOINT_SENTINEL = object()

_CACHE_SLOT_PREFIX = "_fpc_"


def _make_slot_accessors(slot_name: str) -> "tuple[Callable, Callable, Callable]":
    """Generate compiled per-property slot accessors via AST compilation.

    Returns ``(cache_get, cache_set, cache_pop)`` with the slot name baked into bytecode:
    direct slot access, no dict indirection.
    """
    ns: dict = {"_sentinel": _FIXPOINT_SENTINEL}
    exec(compile(
        f"def _cache_get(instance, _sentinel=_sentinel):\n"
        f"    try:\n"
        f"        return instance.{slot_name}\n"
        f"    except AttributeError:\n"
        f"        return _sentinel\n"
        f"def _cache_set(instance, value):\n"
        f"    instance.{slot_name} = value\n"
        f"def _cache_pop(instance):\n"
        f"    try:\n"
        f"        value = instance.{slot_name}\n"
        f"    except AttributeError:\n"
        f"        return None\n"
        f"    del instance.{slot_name}\n"
        f"    return value\n",
        f"<fixpoint-slot-{slot_name}>", "exec",
    ), ns)
    return ns["_cache_get"], ns["_cache_set"], ns["_cache_pop"]


def _make_dict_accessors(attr_name: str) -> "tuple[Callable, Callable, Callable]":
    """Generate compiled per-property dict accessors via AST compilation.

    Returns ``(cache_get, cache_set, cache_pop)`` with the attribute name baked into bytecode.
    """
    ns: dict = {"_sentinel": _FIXPOINT_SENTINEL}
    exec(compile(
        f"def _cache_get(instance, _sentinel=_sentinel):\n"
        f"    return instance.__dict__.get({attr_name!r}, _sentinel)\n"
        f"def _cache_set(instance, value):\n"
        f"    instance.__dict__[{attr_name!r}] = value\n"
        f"def _cache_pop(instance):\n"
        f"    return instance.__dict__.pop({attr_name!r}, None)\n",
        f"<fixpoint-dict-{attr_name}>", "exec",
    ), ns)
    return ns["_cache_get"], ns["_cache_set"], ns["_cache_pop"]


def fixpoint_slotted(cls: type) -> type:
    """Class decorator: add ``_fpc_*`` cache slots for each ``fixpoint_cached_property`` on ``cls``.

    Scans ``cls`` for ``fixpoint_cached_property`` descriptors, adds a dedicated cache slot
    for each one (named ``_fpc_{property_name}``), and rebuilds the class with augmented
    ``__slots__``. This removes the need to manually declare cache slots.

    Usage::

        @fixpoint_slotted
        class Thunk:
            __slots__ = ("callee", "argument")

            @fixpoint_cached_property(bottom=lambda: _BOTTOM)
            def weak_head_normal_form(self) -> object: ...
    """
    extra_slots = []
    for name, value in vars(cls).items():
        if isinstance(value, (fixpoint_cached_property, _fixpoint_dependent_property)):
            extra_slots.append(_CACHE_SLOT_PREFIX + name)
    if not extra_slots:
        return cls
    existing_slots = getattr(cls, "__slots__", ())
    new_slots = tuple(existing_slots) + tuple(extra_slots)
    member_descriptor_type = type(type.__dict__["__module__"]) if "__module__" not in existing_slots else None
    ns = {}
    for key, value in vars(cls).items():
        if key in ("__slots__", "__dict__", "__weakref__"):
            continue
        if isinstance(value, type) and issubclass(value, type):
            continue
        if member_descriptor_type is not None and type(value).__name__ == "member_descriptor":
            continue
        ns[key] = value
    ns["__slots__"] = new_slots
    ns["__qualname__"] = cls.__qualname__
    new_cls = type(cls)(cls.__name__, cls.__bases__, ns)
    for name, value in vars(new_cls).items():
        if isinstance(value, (fixpoint_cached_property, _fixpoint_dependent_property)):
            value._bind_accessors(new_cls)
    return new_cls


def _clear_fixpoint_attr(instance: object, attr_name: str) -> object | None:
    """Pop a cached fixpoint value from an instance, handling both dict and slot modes."""
    if type(instance).__dictoffset__ != 0:
        return instance.__dict__.pop(attr_name, None)
    slot_name = _CACHE_SLOT_PREFIX + attr_name
    try:
        value = getattr(instance, slot_name)
    except AttributeError:
        return None
    delattr(instance, slot_name)
    return value


# Registry of attribute names that need clearing during fixpoint digest cycles.
# Populated by fixpoint_cached_property and fixpoint_dependent decorators.
_fixpoint_clearable_attrs: set[str] = set()


def _accumulate_defaultdict_set(
    accumulator: defaultdict[object, set[object]],
    new_result: defaultdict[object, set[object]],
) -> bool:
    """Merge new_result into accumulator (pointwise set union).

    Returns True if accumulator grew (new entries were added).
    """
    changed = False
    for key, values in new_result.items():
        existing = accumulator[key]
        old_size = len(existing)
        existing.update(values)
        if len(existing) > old_size:
            changed = True
    return changed


class FixpointIterationSentinel(Enum):
    UNLIMITED = math.inf


class fixpoint_cached_property:
    """A cached_property that supports mutual-recursion via least fixpoint iteration.

    API-compatible with functools.cached_property. When reentry is detected
    (mutual recursion), returns the previous iteration's approximation
    (or ``bottom()`` on the first iteration). The outermost caller drives
    a digest loop until values stabilize (no reentry occurs in a round).

    Usage::

        @fixpoint_cached_property(bottom=lambda: defaultdict(set))
        def qualified_this(self):
            ...

    The class-level ``max_fixpoint_iterations`` ContextVar controls the
    maximum number of digest rounds.  ``0`` disables fixpoint iteration
    and raises ``FixpointRecursionError`` on reentry.  Default
    ``FixpointIterationSentinel.UNLIMITED`` iterates until convergence or
    until Python's stack is exhausted::

        fixpoint_cached_property.max_fixpoint_iterations.set(0)   # single-pass
        fixpoint_cached_property.max_fixpoint_iterations.set(100) # bounded multi-pass
        fixpoint_cached_property.max_fixpoint_iterations.set(FixpointIterationSentinel.UNLIMITED) # unbounded (default)

    TODO (trampoline to lift the Python 3.12+ recursion ceiling): when a property's body accesses the
    same property on child nodes, the descent recurses through ``__get__`` once per level, and each
    level goes through the descriptor protocol (the C ``__getattribute__`` -> ``__get__`` call). Those C
    frames count toward CPython 3.12+'s fixed ``Py_C_RECURSION_LIMIT``, which ``sys.setrecursionlimit``
    and a larger thread stack do NOT lift, so a deep term overflows at ~5,000 levels even inside
    ``run_in_large_stack``. This is the sole blocker that makes the deep ``input_quote_defun`` artifact
    (and the self-compilation bootstrap) buildable on CPython 3.11 / PyPy 3.11 only; plain Python
    recursion and ``ast.unparse`` are pure Python and stay liftable. Measured on CPython 3.13: a
    recursive ``loose_bound`` over a 50,000-deep term fails at ~4,998 levels, while the same computation
    on an explicit stack succeeds at the default recursion limit. Driving the descent from an explicit
    work-stack (e.g. a generator-driven trampoline: the property body yields each child-property request
    and this driver resolves dependencies bottom-up, preserving ``bottom``/``merge``/``accumulate`` and
    the reentry digest loop) would remove the C-stack frames per level and lift the ceiling.
    """

    max_fixpoint_iterations: ClassVar[ContextVar[int | FixpointIterationSentinel]] = ContextVar(
        "fixpoint_cached_property.max_fixpoint_iterations", default=FixpointIterationSentinel.UNLIMITED
    )

    def __init__(
        self,
        func: Callable = None,
        *,
        bottom: Callable[[], object],
        accumulate: Callable[[object, object], bool] | None = None,
        merge: Callable[[object, object], object] | None = None,
    ) -> None:
        # Support both @fixpoint_cached_property(bottom=...) and direct call
        if accumulate is not None and merge is not None:
            raise ValueError("fixpoint_cached_property: pass at most one of accumulate / merge")
        self._bottom = bottom
        self._accumulate = accumulate
        self._merge = merge
        self._cache_get = self._cache_set = self._cache_pop = None
        if func is not None:
            self.func: Callable = func
            self.attrname: str = func.__name__
            self.__doc__ = func.__doc__
            _fixpoint_clearable_attrs.add(self.attrname)

    def __call__(self, func: Callable) -> "fixpoint_cached_property":
        """Support @fixpoint_cached_property(bottom=...) decorator syntax."""
        self.func = func
        self.attrname = func.__name__
        self.__doc__ = func.__doc__
        _fixpoint_clearable_attrs.add(self.attrname)
        return self

    def __set_name__(self, owner: type, name: str) -> None:
        if not hasattr(self, "attrname"):
            self.attrname = name
        _fixpoint_clearable_attrs.add(self.attrname)
        self._bind_accessors(owner)

    def _bind_accessors(self, owner: type) -> None:
        """Generate compiled cache accessors, dispatching by slot vs dict."""
        slot_name = _CACHE_SLOT_PREFIX + self.attrname
        if slot_name in getattr(owner, "__slots__", ()):
            self._cache_get, self._cache_set, self._cache_pop = _make_slot_accessors(slot_name)
        else:
            self._cache_get, self._cache_set, self._cache_pop = _make_dict_accessors(self.attrname)

    def _ensure_accessors(self, instance: object) -> None:
        """Lazily bind accessors when __set_name__ was not called (e.g. manually defined classes)."""
        if self._cache_get is not None:
            return
        self._bind_accessors(type(instance))

    @classmethod
    def _get_max_iterations(cls) -> int | float:
        raw = cls.max_fixpoint_iterations.get()
        if isinstance(raw, FixpointIterationSentinel):
            return raw.value
        return raw

    def __get__(self, instance: object, owner: type = None) -> object:
        if instance is None:
            return self

        self._ensure_accessors(instance)
        cache_get = self._cache_get
        cache_set = self._cache_set

        # Fast path: already cached
        value = cache_get(instance)
        if value is not _FIXPOINT_SENTINEL:
            max_iterations = self._get_max_iterations()
            if max_iterations == 0:
                return value
            context = _fixpoint_context_var.get()
            if context is not None:
                key = (id(instance), self.attrname)
                if key in context.computing:
                    context.reentrant = True
                    context.add_participant(instance)
            return value

        max_iterations = self._get_max_iterations()
        context = _fixpoint_context_var.get()
        instance_id = id(instance)
        key = (instance_id, self.attrname)

        if context is None:
            context = _FixpointContext(
                clearable_attr_names=frozenset(_fixpoint_clearable_attrs)
            )
            token = _fixpoint_context_var.set(context)
            try:
                if max_iterations == 0:
                    context.computing.add(key)
                    result = self.func(instance)
                    cache_set(instance, result)
                    return result

                approximation = self._bottom()
                accumulator = self._bottom() if self._accumulate is not None else None
                previous_result = _FIXPOINT_SENTINEL
                for iteration in itertools.count():
                    context.computing.add(key)
                    context.add_participant(instance)
                    result = self.func(instance)

                    if not context.reentrant:
                        cache_set(instance, result)
                        return result

                    if self._accumulate is not None:
                        changed = self._accumulate(accumulator, result)
                        if not changed and iteration > 0:
                            cache_set(instance, accumulator)
                            return accumulator
                        approximation = accumulator
                    elif self._merge is not None:
                        merged = self._merge(approximation, result)
                        if merged == approximation and iteration > 0:
                            cache_set(instance, merged)
                            return merged
                        approximation = merged
                    else:
                        if result == previous_result:
                            cache_set(instance, result)
                            return result
                        previous_result = result
                        approximation = result

                    cache_set(instance, approximation)
                    context.clear_participant_caches()
                    cache_set(instance, approximation)
                    context.computing.clear()
                    context.reentrant = False

                    if iteration + 1 >= max_iterations:
                        raise FixpointRecursionError(
                            f"fixpoint_cached_property '{self.attrname}' did not converge "
                            f"after {max_iterations} iterations",
                            incomplete_result=approximation,
                        )
            finally:
                _fixpoint_context_var.reset(token)
        elif key in context.computing:
            context.reentrant = True
            context.add_participant(instance)
            if max_iterations == 0:
                raise FixpointRecursionError(
                    f"fixpoint_cached_property '{self.attrname}': "
                    f"reentry detected with max_fixpoint_iterations=0",
                    incomplete_result=self._bottom(),
                )
            approximation = cache_get(instance)
            if approximation is not _FIXPOINT_SENTINEL:
                return approximation
            saved = context.approximations.get(key, _FIXPOINT_SENTINEL)
            if saved is not _FIXPOINT_SENTINEL:
                return saved
            return self._bottom()
        else:
            context.computing.add(key)
            context.add_participant(instance)
            result = self.func(instance)
            context.computing.discard(key)
            cache_set(instance, result)
            return result

    def __set__(self, instance: object, value: object) -> None:
        """Data descriptor setter to ensure __get__ is always called."""
        self._ensure_accessors(instance)
        self._cache_set(instance, value)


class _fixpoint_dependent_property:
    """A cached_property that registers its instance as a fixpoint participant.

    Behaves like ``functools.cached_property`` but, when computed inside an
    active fixpoint context, registers the instance so that
    ``clear_participant_caches`` will clear the cached value between
    iterations.  Without this, stale values computed from an incomplete
    fixpoint approximation survive across iterations.
    """

    def __init__(self, func: Callable) -> None:
        self.func = func
        self.attrname = func.__name__
        self.__doc__ = func.__doc__
        self._cache_get = self._cache_set = self._cache_pop = None
        _fixpoint_clearable_attrs.add(self.attrname)

    def __set_name__(self, owner: type, name: str) -> None:
        if not hasattr(self, "attrname"):
            self.attrname = name
        _fixpoint_clearable_attrs.add(self.attrname)
        self._bind_accessors(owner)

    def _bind_accessors(self, owner: type) -> None:
        slot_name = _CACHE_SLOT_PREFIX + self.attrname
        if slot_name in getattr(owner, "__slots__", ()):
            self._cache_get, self._cache_set, self._cache_pop = _make_slot_accessors(slot_name)
        else:
            self._cache_get, self._cache_set, self._cache_pop = _make_dict_accessors(self.attrname)

    def _ensure_accessors(self, instance: object) -> None:
        if self._cache_get is not None:
            return
        self._bind_accessors(type(instance))

    def __get__(self, instance: object, owner: type = None) -> object:
        if instance is None:
            return self

        self._ensure_accessors(instance)
        value = self._cache_get(instance)
        if value is not _FIXPOINT_SENTINEL:
            return value

        if fixpoint_cached_property._get_max_iterations() > 0:
            context = _fixpoint_context_var.get()
            if context is not None:
                context.add_participant(instance)

        value = self.func(instance)
        self._cache_set(instance, value)
        return value


def fixpoint_dependent(func: Callable) -> _fixpoint_dependent_property:
    """Mark a cached_property as dependent on fixpoint_cached_property values.

    During fixpoint digest cycles, these caches are cleared between iterations
    so they are recomputed with updated approximations.

    Usage::

        @fixpoint_dependent
        @cached_property
        def symbol_kind(self):
            ...

    Or equivalently::

        @fixpoint_dependent
        def symbol_kind(self):
            ...
    """
    if isinstance(func, cached_property):
        return _fixpoint_dependent_property(func.func)
    else:
        return _fixpoint_dependent_property(func)
