"""The edit-distance trace is observed from the instrumented interpreter, so its shape is checked here.

The trace must show every subproblem computed exactly once and every later occurrence as a cache hit that
reuses an already-computed subproblem; the distances it records must match a textbook reference; and the
committed listing the paper inputs must be exactly what the generator produces.
"""

from __future__ import annotations

from co_lambda_examples._editdistance_trace import _LEFT, _OUTPUT, _RIGHT, record_trace, render_trace


def _reference(left: str, right: str) -> int:
    """The textbook O(mn) edit-distance table, the reference the observed distances must agree with."""
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


def test_each_subproblem_is_computed_exactly_once() -> None:
    events = record_trace("ab", "cd")
    computes = [(event.left_suffix, event.right_suffix) for event in events if event.kind == "compute"]
    assert len(computes) == len(set(computes)) == 9  # the (m+1)(n+1) distinct suffix-pair states


def test_a_hit_reuses_an_already_computed_subproblem() -> None:
    events = record_trace("ab", "cd")
    computed: "set[tuple[str, str]]" = set()
    hits = 0
    for event in events:
        key = (event.left_suffix, event.right_suffix)
        if event.kind == "compute":
            assert key not in computed, f"{key} computed twice"
            computed.add(key)
        else:
            assert event.kind == "hit"
            assert key in computed, f"hit on {key} before it was computed"
            hits += 1
    assert hits > 0  # the collapse is the reuse; there must be some


def test_recorded_distances_match_the_reference() -> None:
    for event in record_trace("ab", "cd"):
        assert event.distance == _reference(event.left_suffix, event.right_suffix)


def test_committed_trace_is_current() -> None:
    assert _OUTPUT.read_text() == render_trace(record_trace(_LEFT, _RIGHT))
