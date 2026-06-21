"""Generate the step-by-step edit-distance trace by instrumenting the interpreter.

The case study's claim is that the interpreter turns the exponential edit-distance recursion into the
dynamic-programming table by tabling: a subproblem is computed once, written to the cache, and reused on
every later occurrence. We do not assert that in prose, we observe it. While the interpreter solves
``ed`` on a tiny instance, two monkey-patches record an ordered event log of the ``ed``-call subproblems:
``compute_weak_head_normal_form`` is called exactly once per term, at its first solve, so wrapping it
records a COMPUTE (and brackets the call so the log is indented by depth); the cache fast path in
``fixpoint_cached_property.__get__`` records a HIT whenever an already-solved subproblem is requested again
from inside another subproblem's solve. The patches are removed afterwards.

A subproblem is the interned node ``App(App(EDIT_DISTANCE, suffix_a), suffix_b)``; everything else the
solver touches (the BinNat arithmetic, the list destructuring) is filtered out. The result is rendered as
an indented call tree: a COMPUTE node nests its children beneath it, and a HIT is a leaf naming a subproblem
solved earlier, so the reuse the tabling buys is visible directly. The listing goes to
``papers/co-lambda/generated/editdistance-trace-full.tex``, ``\\input`` by the paper.

``co-lambda-editdistance-trace`` (``python -m co_lambda_examples._editdistance_trace``) rewrites it.
"""

from __future__ import annotations

import sys

from dataclasses import dataclass
from pathlib import Path
from typing import final

import co_lambda._ast as ast_module
import co_lambda._shape as shape_module

from co_lambda._ast import App, Node
from co_lambda._dsl import _AppBuilder, app, build, lam
from co_lambda._pyast import binnat_to_int
from fixpoints._core import _FIXPOINT_SENTINEL, _clear_fixpoint_attr, fixpoint_cached_property

from co_lambda_examples._editdistance import EDIT_DISTANCE, _string_to_list

_REPO_ROOT = Path(__file__).resolve().parents[4]
_OUTPUT = _REPO_ROOT / "papers" / "co-lambda" / "generated" / "editdistance-trace-full.tex"

_RECURSION_LIMIT = 100_000

_LEFT = "ab"
_RIGHT = "cd"


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class TraceEvent:
    """One observed step: a subproblem ``(left_suffix, right_suffix)`` either freshly computed or reused
    from the cache, at ``depth`` in the call tree, with the edit distance the solve returns."""

    kind: str  # "compute" or "hit"
    left_suffix: str
    right_suffix: str
    depth: int
    distance: int


def _edit_distance_heads() -> "frozenset[int]":
    """The ``id``s a subproblem's head can take: the ``EDIT_DISTANCE`` node (the top call) and the ``Y``
    self-application the recursion binds the recursive ``edit`` to, ``(\\x. F (x x)) (\\x. F (x x))`` for
    ``F`` the abstraction ``EDIT_DISTANCE`` applies ``Y`` to."""
    assert isinstance(EDIT_DISTANCE, _AppBuilder), "EDIT_DISTANCE is Y applied to the recursive body"
    recursive_body = EDIT_DISTANCE._argument
    self_application = app(
        lam(lambda x: app(recursive_body, app(x, x))),
        lam(lambda x: app(recursive_body, app(x, x))),
    )
    return frozenset({id(build(EDIT_DISTANCE)), id(build(self_application))})


def _suffix_node_ids(text: str, alphabet: "dict[str, int]") -> "dict[int, str]":
    """``id`` of each suffix's Scott-list node mapped to the suffix string, for recognising subproblems."""
    return {
        id(build(_string_to_list(text[index:], alphabet))): text[index:]
        for index in range(len(text) + 1)
    }


def record_trace(left: str, right: str) -> "tuple[TraceEvent, ...]":
    """Solve ``ed left right`` with the interpreter instrumented, returning the ordered subproblem events."""
    alphabet = {character: index for index, character in enumerate(sorted(set(left + right)))}
    left_ids = _suffix_node_ids(left, alphabet)
    right_ids = _suffix_node_ids(right, alphabet)
    edit_distance_heads = _edit_distance_heads()

    def subproblem(node: Node) -> "tuple[str, str] | None":
        # A subproblem is the edit-distance function applied to two suffixes. The head is either the
        # EDIT_DISTANCE node (the top call) or the Y self-application the recursion binds the recursive
        # ``edit`` to; the head check is needed because small Scott structures collide (the empty suffix,
        # the BinNat zero, and the character code 0 are all nil), so the arguments alone are ambiguous.
        if isinstance(node, App) and isinstance(node.function, App) and id(node.function.function) in edit_distance_heads:
            left_suffix = left_ids.get(id(node.function.argument))
            right_suffix = right_ids.get(id(node.argument))
            if left_suffix is not None and right_suffix is not None:
                return left_suffix, right_suffix
        return None

    events: "list[tuple[str, Node, int]]" = []
    stack: "list[Node]" = []
    original_compute = shape_module.compute_weak_head_normal_form
    original_get = fixpoint_cached_property.__get__

    def traced_compute(node: Node):
        recognised = subproblem(node)
        if recognised is not None:
            events.append(("compute", node, len(stack)))
            stack.append(node)
        try:
            return original_compute(node)
        finally:
            if recognised is not None:
                stack.pop()

    def traced_get(self, instance, owner=None):
        if instance is not None and stack and self.attrname == "weak_head_normal_form":
            self._ensure_accessors(instance)
            if self._cache_get(instance) is not _FIXPOINT_SENTINEL and subproblem(instance) is not None:
                events.append(("hit", instance, len(stack)))
        return original_get(self, instance, owner)

    # The weak-head-normal-form cache is global and persistent, so a term solved by an earlier call would
    # be read straight from the cache and expose no COMPUTE events. Clear it first, so the trace observes
    # the whole solve every time and is identical to a fresh process's.
    for node in list(ast_module._canonical.values()):
        _clear_fixpoint_attr(node, "weak_head_normal_form")

    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous_limit, _RECURSION_LIMIT))
    shape_module.compute_weak_head_normal_form = traced_compute
    fixpoint_cached_property.__get__ = traced_get
    try:
        binnat_to_int(build(app(app(EDIT_DISTANCE, _string_to_list(left, alphabet)),
                                _string_to_list(right, alphabet))))
    finally:
        fixpoint_cached_property.__get__ = original_get
        shape_module.compute_weak_head_normal_form = original_compute
        sys.setrecursionlimit(previous_limit)

    distance_of = {(left_suffix, right_suffix): binnat_to_int(node)
                   for (_kind, node, _depth) in events
                   for (left_suffix, right_suffix) in (subproblem(node),)}
    return tuple(
        TraceEvent(kind=kind, left_suffix=left_suffix, right_suffix=right_suffix, depth=depth,
                   distance=distance_of[(left_suffix, right_suffix)])
        for (kind, node, depth) in events
        for (left_suffix, right_suffix) in (subproblem(node),)
    )


def _scott_list(text: str) -> str:
    """A string as the Scott list its characters' BinNat codes form: ``"ab"`` is ``cons a (cons b nil)``."""
    if not text:
        return "nil"
    rest = _scott_list(text[1:])
    return f"cons {text[0]} {rest if rest == 'nil' else f'({rest})'}"


def render_trace(events: "tuple[TraceEvent, ...]") -> str:
    """The committed LaTeX fragment: the event log as an indented call tree in an ``lstlisting``."""
    header = (
        "% Generated by co_lambda_examples._editdistance_trace (co-lambda-editdistance-trace). Do not edit;\n"
        "% regenerate with: python -m co_lambda_examples._editdistance_trace\n"
    )
    def argument(text: str) -> str:
        rendered = _scott_list(text)
        return rendered if rendered == "nil" else f"({rendered})"

    lines = [
        f"{'  ' * event.depth}{event.kind} ed {argument(event.left_suffix)} {argument(event.right_suffix)}"
        f" = {event.distance}"
        for event in events
    ]
    listing = "\\begin{lstlisting}[language=]\n" + "\n".join(lines) + "\n\\end{lstlisting}\n"
    return header + "\n" + listing


def main() -> None:
    events = record_trace(_LEFT, _RIGHT)
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(render_trace(events))
    computes = sum(1 for event in events if event.kind == "compute")
    hits = sum(1 for event in events if event.kind == "hit")
    print(f"wrote {_OUTPUT} ({computes} computes, {hits} hits)")


if __name__ == "__main__":
    main()
