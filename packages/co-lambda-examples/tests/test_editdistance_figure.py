"""The edit-distance trace figure is generated from the interpreter, so its data is checked here.

``build_trace`` reads each suffix-pair distance off the interpreter and, as it builds the trace, asserts
that the interpreter materialised exactly the ``(m+1)(n+1)`` distinct ``ed``-call states the
dynamic-programming table has. These tests cross-check those distances against a textbook reference and
the naive-call count against an independent recursion, and confirm the committed LaTeX artifact the paper
inputs is the one the generator currently produces, so it cannot go stale.
"""

from __future__ import annotations

import pytest

from co_lambda_examples._editdistance_figure import (
    _LEFT,
    _OUTPUT,
    _RIGHT,
    build_trace,
    render_tikz,
)


def _reference(left: str, right: str) -> int:
    """The textbook O(mn) edit-distance table, the reference the interpreter's distances must agree with."""
    rows, columns = len(left), len(right)
    table = [[0] * (columns + 1) for _ in range(rows + 1)]
    for row in range(rows + 1):
        table[row][0] = row
    for column in range(columns + 1):
        table[0][column] = column
    for row in range(1, rows + 1):
        for column in range(1, columns + 1):
            table[row][column] = min(
                table[row - 1][column] + 1,
                table[row][column - 1] + 1,
                table[row - 1][column - 1] + (0 if left[row - 1] == right[column - 1] else 1),
            )
    return table[rows][columns]


def _naive_calls(left: str, right: str) -> int:
    """An independent count of the calls the unmemoised recursion makes, the figure's blow-up number."""
    if not left or not right:
        return 1
    if left[0] == right[0]:
        return 1 + _naive_calls(left[1:], right[1:])
    return 1 + _naive_calls(left[1:], right[1:]) + _naive_calls(left[1:], right) + _naive_calls(left, right[1:])


@pytest.mark.parametrize("left, right", [("ab", "cd"), ("ab", "ac"), ("cat", "cot"), ("", "abc")])
def test_trace_data_matches_reference(left: str, right: str) -> None:
    trace = build_trace(left, right)
    for row, left_suffix in enumerate(trace.left_suffixes):
        for column, right_suffix in enumerate(trace.right_suffixes):
            assert trace.distances[row][column] == _reference(left_suffix, right_suffix)
    assert trace.distinct_states == len(trace.left_suffixes) * len(trace.right_suffixes)
    assert trace.naive_calls == _naive_calls(left, right)


def test_committed_figure_is_current() -> None:
    assert _OUTPUT.read_text() == render_tikz(build_trace(_LEFT, _RIGHT))
