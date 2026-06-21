"""Omega: an unproductive term the solver decides as bottom, traced at the term level.

``Omega = (lambda x. x x) (lambda x. x x)``: its one head beta-contraction returns ``Omega`` itself.
Ordinary reduction loops forever; the solver does not. Because terms are interned the contractum is the
*same node* as ``Omega``, so the solver re-enters a term still on its stack with no layer exposed, and its
running approximation, bottom, is returned and stabilizes: the unproductive loop is decided as bottom in
finite time. This module reads both facts off the implementation, the self-contraction (an interning
identity) and the bottom verdict, and renders a term-level trace parallel to the cyclic-stream one, so the
figure and trace generators (``_omega_figure``, ``_omega_trace``) report what the interpreter actually does.
"""

from __future__ import annotations

from co_lambda._ast import BOTTOM, App, Lam, Node, Var, substitute
from co_lambda._dsl import app, build
from co_lambda._prelude import SELF_APPLY
from co_lambda._shape import weak_head_normalize

# omega = lambda x. x x; Omega = omega omega.
SELF_APPLY_NODE: Node = build(SELF_APPLY)
OMEGA_BUILDER = app(SELF_APPLY, SELF_APPLY)
OMEGA: Node = build(OMEGA_BUILDER)

_BINDER_POOL = "xyzuvw"


def self_contraction() -> Node:
    """The term ``Omega`` head-beta-contracts to: ``(x x)[x := lambda x. x x]``. Returns the contractum,
    which interning makes the same node as ``Omega`` itself (asserted by the caller)."""
    assert isinstance(SELF_APPLY_NODE, Lam), "omega = lambda x. x x is an abstraction"
    return substitute(SELF_APPLY_NODE.body, depth=0, argument=SELF_APPLY_NODE)


def solve_omega() -> None:
    """Check the two observed facts the case study reports: ``Omega`` contracts to itself (the re-entry the
    solver detects), and its weak head normal form is bottom (the unproductive loop, decided in finite time
    because this call returns at all)."""
    assert self_contraction() is OMEGA, "Omega's head contractum is Omega itself (the same interned node)"
    assert weak_head_normalize(OMEGA) is BOTTOM, "Omega is unproductive: its weak head normal form is bottom"


def render_term(node: Node, binders: "tuple[str, ...]" = ()) -> str:
    """Render a closed pure term in ASCII lambda syntax, binders named from a small pool by depth."""
    if isinstance(node, Var):
        return binders[len(binders) - 1 - node.index]
    if isinstance(node, Lam):
        name = _BINDER_POOL[len(binders)]
        return f"\\{name}. {render_term(node.body, (*binders, name))}"
    if isinstance(node, App):
        function = render_term(node.function, binders)
        if isinstance(node.function, Lam):
            function = f"({function})"
        argument = render_term(node.argument, binders)
        if isinstance(node.argument, (Lam, App)):
            argument = f"({argument})"
        return f"{function} {argument}"
    raise TypeError(f"cannot render {node!r}")


def trace_lines() -> "tuple[str, ...]":
    """The term-level trace, read off the real interpreter: ``Out`` on ``Omega`` runs ``WHNF``, which
    contracts the head redex to ``Omega`` itself; the solver re-enters that term while it is still on the
    stack with no layer exposed and returns bottom. Parallel to the cyclic-stream trace."""
    contractum = self_contraction()
    assert contractum is OMEGA, "Omega's head contractum must be Omega itself"
    assert weak_head_normalize(OMEGA) is BOTTOM, "Omega's weak head normal form must be bottom"
    omega = render_term(OMEGA)
    contracted = render_term(contractum)
    return (
        "Out Omega:",
        f"  WHNF:  {omega}  ->  {contracted}   (head redex contracts to Omega itself, the same interned term)",
        "  re-enter Omega: on the stack, no layer exposed  ->  bottom",
        "Omega = bottom",
    )
