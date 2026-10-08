"""Weak head normalization: a term's outermost constructor, computed as a least fixpoint by tabling.

``weak_head_normalize`` exposes a node's outermost constructor after weak head reduction (it stops
at the outermost constructor and does not reduce under ``lambda``). A deterministic calculus
exposes exactly one constructor at a node, so the value is a single node (an interpreter
``Var``/``Lam``/``App`` or a compiled ``Closure``) or ``BOTTOM`` (no constructor), never a set. A
compiled ``Thunk`` (a redex) forces through ``apply_value``, the application path shared with ``App``.
``compute_weak_head_normal_form`` is the per-node clause body; ``Node.weak_head_normal_form`` wraps
it in a ``fixpoint_cached_property`` resolved as a least fixpoint from ``BOTTOM`` upward. Because
nodes are interned, a node reached again during its own computation is caught by a pointer test; an
unproductive cycle (a re-entry with no constructor exposed, as in ``Omega`` or ``Y (lambda x. x)``)
stabilizes at ``BOTTOM``.

A reduction budget (a context variable) bounds beta-reduction so a genuinely non-rational reduction
surfaces as ``ReductionBudgetExceeded`` instead of hanging.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Iterator, cast, final

from tablambda._ast import (
    BOTTOM,
    App,
    Lam,
    Node,
    WeakHeadBottom,
    Var,
    make_app,
    substitute,
)
from tablambda._defun_runtime import Closure, Thunk


class ReductionBudgetExceeded(RuntimeError):
    """Raised when a bounded reduction runs out of beta-steps (a divergent term)."""


@final
@dataclass(kw_only=True, slots=True, weakref_slot=True)
class _Budget:
    remaining: int = field(default=0)


_reduction_budget: ContextVar[_Budget | None] = ContextVar(
    "tablambda._reduction_budget", default=None
)


@contextmanager
def reduction_budget(steps: int) -> Iterator[None]:
    """Bound beta-reduction to ``steps`` head redexes within this context."""
    if steps <= 0:
        raise ValueError("reduction budget must be positive")
    token = _reduction_budget.set(_Budget(remaining=steps))
    try:
        yield
    finally:
        _reduction_budget.reset(token)


def _consume_redex() -> None:
    budget = _reduction_budget.get()
    if budget is None:
        return
    if budget.remaining <= 0:
        raise ReductionBudgetExceeded("reduction budget exhausted")
    budget.remaining -= 1


def weak_head_normalize(node: Node) -> Node | WeakHeadBottom:
    """The weak head normal form of ``node``: its outermost constructor, or ``BOTTOM`` (none).

    Typed via ``Node.weak_head_normal_form`` (a ``fixpoint_cached_property`` typed as ``object``).
    """
    return cast("Node | WeakHeadBottom", node.weak_head_normal_form)


def apply_value(head: Node, argument: Node) -> Node | WeakHeadBottom:
    """Apply a weak-head VALUE ``head`` to ``argument``, returning the node to continue normalizing
    (or ``BOTTOM``). ``head`` must already be in weak head normal form, so it is never a ``Thunk``.

    This is the one application path shared by the interpreter's ``App`` clause and the compiled
    ``Thunk.force``, so an interpreter ``Lam`` and a compiled ``Closure`` apply uniformly and the two
    worlds run mixed: firing a ``Lam`` substitutes (consuming the reduction budget), calling a
    ``Closure`` runs the compiled body, and a neutral head builds the application node.
    """
    match head:
        case Lam(body=lambda_body):
            _consume_redex()
            return substitute(lambda_body, depth=0, argument=argument)
        case Closure():
            return head(argument)
        case Var() | App():
            return make_app(head, argument)
        case WeakHeadBottom.BOTTOM:
            return BOTTOM
        case _:
            raise TypeError(f"Cannot apply non-value {head!r}")


def compute_weak_head_normal_form(node: Node) -> Node | WeakHeadBottom:
    """The per-node clause body of weak head normalization; single-valued, no aggregate."""
    match node:
        case Var():
            return node
        case Lam():
            return node
        case Closure():
            return node
        case Thunk():
            return node.force()
        case App(function=function, argument=argument):
            head = weak_head_normalize(function)
            match head:
                case Var() | App():
                    # FIXME: this exposes the real weak head normal form, and the fixpoint machinery
                    # cannot yet carry it. `test_scott_ast_decodes_and_executes` raises
                    # RecursionError from `fixpoints._core.fixpoint_cached_property` when it runs
                    # against a cold cache, and passes when earlier tests have already normalized
                    # the shared interned nodes; measured over `--randomly-seed` 1 to 6 on
                    # `test_pyast.py`, seeds 1 and 3 fail and the other four pass.
                    # The previous code returned `node`, the unreduced application, which hid this
                    # bug behind a second one: the exposed layer was then a representative of the
                    # weak head normal form rather than the normal form, and Lemma A.2 in the paper
                    # was worded to match that. The same definition in SWI-Prolog, tabled and with
                    # no interning, handles every term tried without recursion trouble, so the
                    # defect is in this fixpoint machinery rather than in the definition. Fix the
                    # recursion here; do not restore the representative.
                    return make_app(head, argument)
                case WeakHeadBottom.BOTTOM:
                    return BOTTOM
                case _:
                    applied = apply_value(head, argument)
                    if applied is BOTTOM:
                        return BOTTOM
                    return weak_head_normalize(applied)
        case _:
            raise TypeError(f"Unknown node {node!r}")
