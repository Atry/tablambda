"""The cyclic-stream trace is read off the interpreter at the term level, so its facts are checked here.

The point of Section~\\ref{sec:application-cycles} is operational: the Scott cons cell hands its callback a
tail that is the self-application ``W W`` (``W = lambda x. (cons 0)(x x)``), not the syntactic root; that
tail is rebuilt by beta on every unfold but interning folds it onto the existing node, so the solver's
second call to ``W W`` is a state still on the stack and it closes a back edge. These tests pin those facts
and confirm the committed artifacts are what the generators produce.
"""

from __future__ import annotations

from co_lambda._ast import make_app
from co_lambda._shape import weak_head_normalize
from co_lambda_examples._cyclic_zeros import (
    STREAM,
    W_APPLIED,
    W_SELF,
    cons_cell,
    head_step,
    walk,
)

from co_lambda_examples import _cyclic_zeros_figure, _cyclic_zeros_trace


def test_the_tail_is_the_self_application_not_the_root() -> None:
    cell = cons_cell(weak_head_normalize(STREAM))
    assert cell is not None
    _head, tail = cell
    assert tail is W_APPLIED  # the tail handed to the callback is W W ...
    assert tail is not STREAM  # ... not the syntactic root r


def test_Y_unfolds_to_the_self_application() -> None:
    assert head_step(STREAM) is W_APPLIED  # r's first head step is W W


def test_self_application_normalizes_to_the_same_cell() -> None:
    assert weak_head_normalize(W_APPLIED) is weak_head_normalize(STREAM)  # same interned cons cell
    cell = cons_cell(weak_head_normalize(W_APPLIED))
    assert cell is not None and cell[1] is W_APPLIED  # its tail is itself: a self-loop


def test_interning_folds_the_rebuilt_tail() -> None:
    assert make_app(W_SELF, W_SELF) is W_APPLIED  # beta rebuilds it, interning folds it onto one node


def test_walk_closes_a_back_edge_on_the_in_progress_state() -> None:
    steps, states = walk()
    assert [state.name for state in states] == ["r", "W W"]
    assert all(state.head == 0 for state in states)
    assert states[0].tail_name == "W W" and not states[0].tail_is_back_edge  # r leads in
    assert states[1].tail_name == "W W" and states[1].tail_is_back_edge  # W W self-loop
    assert any("back edge" in step.text for step in steps)


def test_committed_trace_is_current() -> None:
    steps, _states = walk()
    assert _cyclic_zeros_trace._OUTPUT.read_text() == _cyclic_zeros_trace.render_trace(steps)


def test_committed_figure_is_current() -> None:
    _steps, states = walk()
    assert _cyclic_zeros_figure._OUTPUT.read_text() == _cyclic_zeros_figure.render_tikz(states)
