"""The lambda-term graph: a first-order de Bruijn tree.

Nodes are identity objects (``eq=False``): node identity is object identity, which the
paper uses as the visited set. The AST is a finite tree; the only source of genuine
sharing / cycles is the ``Mu`` recursion binder, which the interpreter resolves to the
same node object at reduction time.

``substitute`` is the load-bearing function for the copy-vs-share distinction: it copies
the redex-body spine into fresh nodes and inserts the argument by reference.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable, cast, final

from fixpoints._core import fixpoint_cached_property, fixpoint_slotted


class ShapeBottom(Enum):
    """The bottom of the shape lattice: no weak-head shape (bottom, an unproductive cycle)."""

    BOTTOM = auto()


BOTTOM = ShapeBottom.BOTTOM


@fixpoint_slotted
@dataclass(kw_only=True, eq=False)
class Node(ABC):
    """A lambda-term-graph node. Identity is object identity (``eq=False``)."""

    __slots__ = ()

    def __repr__(self) -> str:
        return f"<{type(self).__name__} 0x{id(self):x}>"

    @fixpoint_cached_property(bottom=lambda: 0)
    def loose_bound(self) -> int:
        """One past the largest free de Bruijn index (``0`` iff the node is closed)."""
        return _loose_bound(self)

    @fixpoint_cached_property(
        bottom=lambda: BOTTOM, merge=lambda left, right: _deep_merge(left, right)
    )
    def weak_head_normal_form(self) -> "Node | ShapeBottom":
        """The weak head normal form: the outermost constructor after weak head reduction, a least
        fixpoint.

        Single-valued (a deterministic calculus exposes one constructor), so not a set. The least
        fixpoint of the weak-head-normalization recurrence, computed from ``BOTTOM`` upward by deep
        merge in the approximation order (``fixpoints``): each round's freshly computed layer is joined
        into the running approximation rather than overwriting it, so the iteration respects the order
        and two incompatible non-``BOTTOM`` layers crash as a conflict. Because nodes are interned, a
        node reached again during its own computation is caught by a pointer test. An unproductive cycle
        (a re-entry with no constructor exposed, as in ``Omega`` or ``Y (lambda x. x)``) stabilizes at
        ``BOTTOM``.
        """
        from co_lambda._shape import compute_weak_head_normal_form

        return compute_weak_head_normal_form(self)

    @fixpoint_cached_property(
        bottom=lambda: BOTTOM, merge=lambda left, right: _deep_merge(left, right)
    )
    def head_normal_form(self) -> "Node | ShapeBottom":
        """The head normal form (the Boehm reading): the outermost constructor after head reduction,
        a least fixpoint.

        Identical to ``weak_head_normal_form`` except that a ``lambda`` whose body has no head normal
        form is itself ``BOTTOM`` here (head reduction continues under the ``lambda``), so the readout
        is the Boehm tree rather than Levy-Longo.
        """
        from co_lambda._shape import compute_head_normal_form

        return compute_head_normal_form(self)

    def __call__(self, *arguments: "Node") -> "Node":
        """Curried application: ``function(a, b, c)`` builds ``make_app(make_app(make_app(function,
        a), b), c)``. Sugar for the nested ``make_app`` chains that applying a node to several
        arguments needs (the node-level counterpart of the HOAS ``app``)."""
        result: Node = self
        for argument in arguments:
            result = make_app(result, argument)
        return result


@final
@dataclass(kw_only=True, eq=False)
class Var(Node):
    __slots__ = ("index",)
    index: int
    """de Bruijn index."""


@final
@dataclass(kw_only=True, eq=False, repr=False)
class Lam(Node):
    __slots__ = ("body",)
    body: Node


@final
@dataclass(kw_only=True, eq=False, repr=False)
class App(Node):
    __slots__ = ("function", "argument")
    function: Node
    argument: Node


@final
@dataclass(kw_only=True, eq=False, repr=False)
class Native(Node):
    """A foreign-function node: a compiled Python callable embedded in the term graph (the FFI).

    ``run`` takes ``arity`` argument ``Node``s and returns a result ``Node``; the Node graph is the
    lingua franca, so a compiled island interoperates with the interpreter by consuming and producing
    nodes. A closed island is ``arity == 0`` (``run()`` builds its result node). The interpreter
    drives it: a saturated native fires ``run`` and continues normalizing the returned node, so a
    compiled island sits inside an otherwise interpreted (folding) graph.

    ``collected`` holds the arguments gathered so far while the native is under-applied (empty for a
    bare native): an ``App`` spine over a native is read back as a ``Native`` whose ``collected`` grows
    one argument at a time until it reaches ``arity`` and fires. A bare native is closed, but a partial
    application's ``loose_bound`` is that of its collected arguments.
    """

    __slots__ = ("run", "arity", "collected")
    run: "Callable[..., Node]"
    arity: int
    collected: "tuple[Node, ...]"


# Hash-consing: structurally-equal nodes (with already-interned children) become the SAME
# object, so node identity is structural identity. This is what makes a cyclic structure a
# finite set of positions: an Omega contractum, or a repeated stream cell produced by a Y
# recursion, interns back to an existing node, so the least-fixpoint merge folds it. No
# recursion binder is needed; Y suffices, since the calculus stays pure.
#
# ``FOL_INTERNER_RETAIN`` selects the cache strategy. One knob, three regimes:
#   "inf" (default): a plain strong dict that never frees -- node identity is permanent, the original
#                    no-GC interner. Full tabling speed; a large compilation (specializing the whole
#                    compiler) retains gigabytes, but that path is gated, so the common case keeps the
#                    fast, simple behaviour with no weakref overhead.
#   "0"            : a ``WeakValueDictionary`` with no retainer -- a key maps to a node iff it is still
#                    alive, so unreferenced reductions are reclaimed by refcounting (minimal memory).
#                    Correctness-safe (the weak map never holds two structurally-equal LIVE nodes, so
#                    cycle folding's pointer test never sees a duplicate), but a dropped node loses its
#                    cached normal form and is recomputed, so tabling speed is lost.
#   N (an int)     : the weak map plus a bounded strong LRU of the N most-recently-used nodes. The LRU
#                    keeps the hot, frequently-reused nodes (and their cached normal forms) alive so
#                    tabling speed is preserved within reuse distance N, while the cold tail is
#                    reclaimed -- memory bounded near max(live working set, N). The retainer only ADDS
#                    strong refs, so it can never create a duplicate.
# The LRU is a stdlib ``OrderedDict`` (C-backed move-to-end / popitem); cachetools / lru-dict were
# considered but add a dependency (and, for lru-dict, a C build under Nix) for no behavioural gain here.
import os as _os
import weakref as _weakref
from collections import OrderedDict as _OrderedDict

_INTERNER_RETAIN = _os.environ.get("FOL_INTERNER_RETAIN", "inf")

_canonical: "dict[tuple[object, ...], Node] | _weakref.WeakValueDictionary[tuple[object, ...], Node]"
_retainer: "_OrderedDict[tuple[object, ...], Node] | None"
if _INTERNER_RETAIN == "inf":
    _canonical = {}  # strong: the original no-GC interner
    _retainer = None
    _retain_max = 0
elif _INTERNER_RETAIN == "0":
    _canonical = _weakref.WeakValueDictionary()
    _retainer = None
    _retain_max = 0
else:
    _canonical = _weakref.WeakValueDictionary()
    _retainer = _OrderedDict()
    _retain_max = int(_INTERNER_RETAIN)


def _retain(key: tuple[object, ...], node: Node) -> None:
    """Mark ``key -> node`` most-recently-used in the bounded LRU retainer (evicting the oldest if over
    the bound). A canonical-map hit may name a node already evicted from the retainer while it stayed
    alive elsewhere, so an absent key is re-inserted rather than moved (move-to-end would raise)."""
    if _retainer is None:
        return
    if key in _retainer:
        _retainer.move_to_end(key)
    else:
        _retainer[key] = node
        if len(_retainer) > _retain_max:
            _retainer.popitem(last=False)


def _intern_node(key: tuple[object, ...], make: Callable[[], Node]) -> Node:
    existing = _canonical.get(key)
    if existing is not None:
        _retain(key, existing)
        return existing
    node = make()
    _canonical[key] = node
    _retain(key, node)
    return node


def make_var(index: int) -> Var:
    return cast(Var, _intern_node(("Var", index), lambda: Var(index=index)))


def make_lam(body: Node) -> Lam:
    return cast(Lam, _intern_node(("Lam", id(body)), lambda: Lam(body=body)))


def make_app(function: Node, argument: Node) -> App:
    return cast(
        App,
        _intern_node(
            ("App", id(function), id(argument)),
            lambda: App(function=function, argument=argument),
        ),
    )


def make_native(
    run: "Callable[..., Node]", arity: int, collected: "tuple[Node, ...]" = ()
) -> Native:
    if arity < 0:
        raise ValueError("native arity must be nonnegative")
    return cast(
        Native,
        _intern_node(
            ("Native", id(run), arity, tuple(id(node) for node in collected)),
            lambda: Native(run=run, arity=arity, collected=collected),
        ),
    )


def _deep_merge(left: "Node | ShapeBottom", right: "Node | ShapeBottom") -> "Node | ShapeBottom":
    """Join two approximations of a node's weak-head/Boehm layer in the approximation order.

    ``BOTTOM`` is least, so it joins to the other side. Two non-``BOTTOM`` layers with the same
    outermost constructor join structurally (their successors merge); two different constructors (or
    ``Var`` indices, or native run/arity) have no upper bound, a conflict that crashes, because a
    deterministic effect must not expose two incompatible layers at one node. Because nodes are
    interned, equal layers share identity and the common case short-circuits without recursing.
    """
    return _deep_merge_into(left, right, {})


def _deep_merge_into(
    left: "Node | ShapeBottom",
    right: "Node | ShapeBottom",
    in_progress: "dict[tuple[int, int], None]",
) -> "Node | ShapeBottom":
    if right is BOTTOM:
        return left
    if left is BOTTOM:
        return right
    if left is right:
        return left
    pair = (id(left), id(right))
    if pair in in_progress:
        raise ValueError(
            "deep merge of two distinct rational layers would not terminate: a node exposed two "
            "incompatible non-bottom layers across rounds"
        )
    in_progress[pair] = None
    try:
        match (left, right):
            case (Var(index=left_index), Var(index=right_index)):
                if left_index != right_index:
                    raise ValueError(f"deep merge conflict: Var {left_index} vs Var {right_index}")
                return left
            case (Lam(body=left_body), Lam(body=right_body)):
                return make_lam(_deep_merge_into(left_body, right_body, in_progress))
            case (
                App(function=left_function, argument=left_argument),
                App(function=right_function, argument=right_argument),
            ):
                return make_app(
                    _deep_merge_into(left_function, right_function, in_progress),
                    _deep_merge_into(left_argument, right_argument, in_progress),
                )
            case (
                Native(run=left_run, arity=left_arity, collected=left_collected),
                Native(run=right_run, arity=right_arity, collected=right_collected),
            ):
                if (
                    left_run is not right_run
                    or left_arity != right_arity
                    or len(left_collected) != len(right_collected)
                ):
                    raise ValueError("deep merge conflict: incompatible natives")
                merged_collected = tuple(
                    _deep_merge_into(left_child, right_child, in_progress)
                    for left_child, right_child in zip(left_collected, right_collected)
                )
                return make_native(left_run, left_arity, merged_collected)
            case _:
                raise ValueError(
                    f"deep merge conflict: {type(left).__name__} vs {type(right).__name__}"
                )
    finally:
        del in_progress[pair]


def _loose_bound(node: Node) -> int:
    match node:
        case Var(index=index):
            return index + 1
        case Lam(body=body):
            return max(0, body.loose_bound - 1)
        case App(function=function, argument=argument):
            return max(function.loose_bound, argument.loose_bound)
        case Native(collected=collected):
            return max((argument.loose_bound for argument in collected), default=0)
        case _:
            raise TypeError(f"Unknown node {node!r}")


def shift(node: Node, *, cutoff: int, amount: int) -> Node:
    """Shift free de Bruijn indices ``>= cutoff`` by ``amount``."""
    if node.loose_bound <= cutoff:
        return node
    match node:
        case Var(index=index):
            return make_var(index + amount)
        case Lam(body=body):
            return make_lam(shift(body, cutoff=cutoff + 1, amount=amount))
        case App(function=function, argument=argument):
            return make_app(
                shift(function, cutoff=cutoff, amount=amount),
                shift(argument, cutoff=cutoff, amount=amount),
            )
        case Native(run=run, arity=arity, collected=collected):
            return make_native(
                run,
                arity,
                tuple(shift(argument, cutoff=cutoff, amount=amount) for argument in collected),
            )
        case _:
            raise TypeError(f"Unknown node {node!r}")


def substitute(node: Node, *, depth: int, argument: Node) -> Node:
    """Capture-avoiding de Bruijn substitution of ``argument`` for ``Var(depth)``."""
    if node.loose_bound <= depth:
        return node
    match node:
        case Var(index=index):
            if index == depth:
                return shift(argument, cutoff=0, amount=depth)
            return make_var(index - 1)
        case Lam(body=body):
            return make_lam(substitute(body, depth=depth + 1, argument=argument))
        case App(function=function, argument=app_argument):
            return make_app(
                substitute(function, depth=depth, argument=argument),
                substitute(app_argument, depth=depth, argument=argument),
            )
        case Native(run=run, arity=arity, collected=collected):
            return make_native(
                run,
                arity,
                tuple(
                    substitute(collected_argument, depth=depth, argument=argument)
                    for collected_argument in collected
                ),
            )
        case _:
            raise TypeError(f"Unknown node {node!r}")
