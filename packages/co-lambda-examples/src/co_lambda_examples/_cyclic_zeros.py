"""The cyclic stream of zeros, traced at the term level the way the solver actually computes it.

``r = Y (cons 0)`` head-reduces to ``W·W`` (with ``W = lambda x. (cons 0)(x x)``, the abstraction ``Y``
builds), which weak-head-normalizes to the Scott cons cell ``cons 0 (W·W)``. The cons cell is a CPS
callback ``lambda c. lambda n. c h t``; the tail ``t`` it hands its caller is ``W·W`` itself, the
self-application ``Y`` produces, a freshly beta-substituted term and not the syntactic root ``r``.

The fold is the genuine interning: each unfold rebuilds ``make_app(W, W)``, but hash-consing returns the
existing node, so the solver's second call to ``W·W`` is a state it is already solving and it closes a
back edge. We read this off the real interpreter: a faithful ``Out``/``WHNF`` walk over the real interned
terms (real ``substitute``/``make_app``), asserting every exposed layer equals ``weak_head_normalize``,
mirroring the pseudocode of Section~\\ref{sec:bridge}. Used by ``_cyclic_zeros_trace`` and
``_cyclic_zeros_figure``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from co_lambda._ast import App, Lam, Node, ShapeBottom, Var, make_app, substitute
from co_lambda._dsl import app, build, lam
from co_lambda._prelude import SCOTT_CONS, Y, ZERO
from co_lambda._pyast import _church_to_int
from co_lambda._shape import weak_head_normalize

# r = Y (cons 0); W = lambda x. (cons 0)(x x) (the abstraction Y builds); W·W = the self-application.
STREAM_BUILDER = app(Y, app(SCOTT_CONS, ZERO))
STREAM: Node = build(STREAM_BUILDER)
W_SELF: Node = build(lam(lambda bound: app(app(SCOTT_CONS, ZERO), app(bound, bound))))
W_APPLIED: Node = make_app(W_SELF, W_SELF)

_CONS_NODE: Node = build(SCOTT_CONS)
_ZERO_NODE: Node = build(ZERO)
_Y_NODE: Node = build(Y)

# Names for the pretty-printer: known interned nodes rendered by name rather than expanded.
_NAMES: "dict[int, str]" = {
    id(_Y_NODE): "Y",
    id(_CONS_NODE): "cons",
    id(_ZERO_NODE): "0",
    id(W_SELF): "W",
    id(W_APPLIED): "W W",
}
_STATE_NAMES: "dict[int, str]" = {id(STREAM): "r", id(W_APPLIED): "W W"}


def cons_cell(node: "Node | ShapeBottom") -> "tuple[Node, Node] | None":
    """The head and tail sub-terms if ``node`` is a Scott cons cell ``lambda c. lambda n. c head tail``."""
    if isinstance(node, Lam) and isinstance(node.body, Lam):
        spine = node.body.body
        if isinstance(spine, App) and isinstance(spine.function, App) and isinstance(spine.function.function, Var):
            return spine.function.argument, spine.argument
    return None


def render_term(node: Node) -> str:
    """Render a term with known nodes named and a cons cell shown in constructor form ``cons h (t)``."""
    if id(node) in _NAMES:
        return _NAMES[id(node)]
    cell = cons_cell(node)
    if cell is not None:
        head, tail = cell
        return f"cons {render_term(head)} ({render_term(tail)})"
    if isinstance(node, Var):
        return f"#{node.index}"
    if isinstance(node, Lam):
        return f"(λ. {render_term(node.body)})"
    if isinstance(node, App):
        return f"({render_term(node.function)} {render_term(node.argument)})"
    raise TypeError(f"cannot render {node!r}")


def head_step(node: Node) -> "Node | None":
    """One weak-head reduction step (contract the head redex along the function spine), or ``None`` if the
    term is already in weak head normal form. Uses the real ``substitute``/``make_app``, so the contractum
    is interned exactly as the interpreter builds it."""
    spine: "list[App]" = []
    current = node
    while isinstance(current, App):
        spine.append(current)
        current = current.function
    if isinstance(current, Lam) and spine:
        redex = spine[-1]
        result = substitute(current.body, depth=0, argument=redex.argument)
        for outer in reversed(spine[:-1]):
            result = make_app(result, outer.argument)
        return result
    return None


def _reduce_to_whnf(node: Node) -> "tuple[Node, ...]":
    """The head-reduction sequence from ``node`` to its weak head normal form, asserted to agree with the
    interpreter's ``weak_head_normalize``."""
    sequence = [node]
    current = node
    while True:
        nxt = head_step(current)
        if nxt is None:
            break
        sequence.append(nxt)
        current = nxt
    assert current is weak_head_normalize(node), "the stepper must reach the interpreter's whnf"
    return tuple(sequence)


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class StreamStep:
    """One line of the term-level trace: an indentation depth and rendered text."""

    depth: int
    text: str


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class StreamState:
    """A solved stream state for the figure: its name, head value, the name of its tail state, and whether
    that tail edge is a back edge (the tail is the state itself or an ancestor still being solved)."""

    name: str
    head: int
    tail_name: str
    tail_is_back_edge: bool


def _strip_outer_parens(text: str) -> str:
    """Strip one fully-enclosing pair of parentheses, so ``(Y (cons 0))`` reads ``Y (cons 0)``."""
    if not (text.startswith("(") and text.endswith(")")):
        return text
    depth = 0
    for index, character in enumerate(text):
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return text[1:-1] if index == len(text) - 1 else text
    return text


def _salient(sequence: "tuple[Node, ...]") -> "tuple[str, ...]":
    """Render the head-reduction sequence to the salient, readable terms: drop the intermediate steps that
    expose only a partial application of ``cons`` (a bare lambda, a de Bruijn index, or the un-normalized
    ``((cons 0) ...)`` redex), strip a fully-enclosing paren pair, and collapse consecutive duplicates, so
    what remains is the term, the ``Y`` unfold, and the exposed cons cell."""
    rendered: "list[str]" = []
    for node in sequence:
        text = render_term(node)
        if "λ." in text or "#" in text or text.startswith("((cons"):
            continue
        text = _strip_outer_parens(text)
        if rendered and rendered[-1] == text:
            continue
        rendered.append(text)
    return tuple(rendered)


def walk() -> "tuple[tuple[StreamStep, ...], tuple[StreamState, ...]]":
    """Run a faithful ``Out``/``WHNF`` walk from ``r`` over the real interned terms, returning the
    term-level trace lines and the solved states (for the figure). A tail already on the stack is a back
    edge (the cycle); the head value is read off the interpreter with ``_church_to_int``."""
    steps: "list[StreamStep]" = []
    states: "list[StreamState]" = []
    on_stack: "list[int]" = []
    solved: "set[int]" = set()

    def state_name(node: Node) -> str:
        return _STATE_NAMES.get(id(node), render_term(node))

    def out(node: Node, depth: int) -> None:
        name = state_name(node)
        on_stack.append(id(node))
        solved.add(id(node))
        sequence = _reduce_to_whnf(node)
        cell = sequence[-1]
        cell_pair = cons_cell(cell)
        assert cell_pair is not None, "the zero stream is productive: every state exposes a cons cell"
        head, tail = cell_pair
        head_value = _church_to_int(head)
        tail_name = state_name(tail)

        steps.append(StreamStep(depth=depth, text=f"Out {name}:"))
        steps.append(StreamStep(depth=depth + 1, text="WHNF:  " + "  ->  ".join(_salient(sequence))))
        steps.append(StreamStep(depth=depth + 1, text=f"compute {name} => cons {head_value} ({tail_name})"))

        tail_back_edge = id(tail) in on_stack
        if tail_back_edge:
            steps.append(StreamStep(depth=depth + 1,
                                    text=f"tail {tail_name}: on the stack -> back edge (cycle closes)"))
        elif id(tail) in solved:
            steps.append(StreamStep(depth=depth + 1, text=f"tail {tail_name}: already tabled -> reuse"))
        states.append(StreamState(name=name, head=head_value, tail_name=tail_name,
                                  tail_is_back_edge=tail_back_edge))
        if not tail_back_edge and id(tail) not in solved:
            out(tail, depth + 1)
        on_stack.pop()

    out(STREAM, 0)
    return tuple(steps), tuple(states)
