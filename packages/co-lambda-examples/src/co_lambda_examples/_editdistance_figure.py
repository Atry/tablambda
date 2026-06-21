"""Generate the edit-distance trace figure for the paper from the real interpreter.

The figure in the edit-distance case study is not drawn by hand: it is produced here from the same
interpreter the paper describes, so it cannot drift from the implementation. For a tiny instance the
generator (1) reads each suffix-pair subproblem's distance straight off the interpreter, (2) confirms,
by scanning the interner, that the interpreter materialised exactly the ``(m+1)(n+1)`` distinct
``ed``-call states the dynamic-programming table has, and (3) counts the calls the naive recursion would
make. It emits a TikZ ``tikzpicture`` of the call graph on the suffix-pair lattice: each distinct state is
one node carrying its distance, an interior state points to the three subproblems it calls, and a state
several callers share (the collapse the tabling buys) is a node with several incoming edges. The paper
floats and captions the picture; this module owns only its body.

``co-lambda-editdistance-figure`` (``python -m co_lambda_examples._editdistance_figure``) rewrites the
committed ``papers/co-lambda/generated/editdistance-trace.tex``.
"""

from __future__ import annotations

import sys

from dataclasses import dataclass
from pathlib import Path
from typing import final

import co_lambda._ast as ast_module

from co_lambda._ast import App
from co_lambda._dsl import app, build
from co_lambda._pyast import binnat_to_int

from co_lambda_examples._editdistance import EDIT_DISTANCE, _string_to_list

_REPO_ROOT = Path(__file__).resolve().parents[4]
_OUTPUT = _REPO_ROOT / "papers" / "co-lambda" / "generated" / "editdistance-trace.tex"

# The interner recursion (substitution) is as deep as the subproblem-dependency diagonal plus the BinNat
# arithmetic; raise the limit for the build and restore it, as the interpreter's own driver does.
_RECURSION_LIMIT = 100_000

# The figure's tiny instance: two length-two strings with all four characters distinct, so the heads
# differ at the root and the three-way branch (substitute, delete, insert) is exercised, making a shared
# subproblem visible. Larger instances stay correct but draw a denser lattice.
_LEFT = "ab"
_RIGHT = "cd"

_GRID_DX = 1.75
_GRID_DY = 1.3


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class EditDistanceTrace:
    """The traced collapse of one tiny edit-distance instance, read from the interpreter.

    Suffixes run from the whole string at index ``0`` to the empty suffix last, so state ``(i, j)`` is the
    pair ``(left_suffixes[i], right_suffixes[j])`` and ``distances[i][j]`` is its edit distance. The
    productive collapse is ``distinct_states == len(left_suffixes) * len(right_suffixes)`` against
    ``naive_calls``, the calls the unmemoised recursion would make.
    """

    left: str
    right: str
    left_suffixes: tuple[str, ...]
    right_suffixes: tuple[str, ...]
    distances: tuple[tuple[int, ...], ...]
    in_degrees: tuple[tuple[int, ...], ...]
    distinct_states: int
    naive_calls: int


def _suffixes(text: str) -> tuple[str, ...]:
    return tuple(text[index:] for index in range(len(text) + 1))


def _children(left_suffix: str, right_suffix: str) -> "tuple[tuple[int, int], ...]":
    """The subproblem index offsets ``ed`` calls from state ``(left_suffix, right_suffix)``.

    An empty side is a base case (its cost is the other length), so it calls nothing. Equal heads recurse
    on both tails; differing heads call all three of substitute, delete, and insert.
    """
    if not left_suffix or not right_suffix:
        return ()
    if left_suffix[0] == right_suffix[0]:
        return ((1, 1),)
    return ((1, 1), (1, 0), (0, 1))


def _naive_call_count(left_suffix: str, right_suffix: str) -> int:
    """The number of calls the unmemoised recursion would make, re-expanding every shared subproblem."""
    return 1 + sum(
        _naive_call_count(left_suffix[delta_left:], right_suffix[delta_right:])
        for delta_left, delta_right in _children(left_suffix, right_suffix)
    )


def build_trace(left: str, right: str) -> EditDistanceTrace:
    """Run the interpreter on ``left``/``right`` and read off the distances, the distinct-state count, and
    the in-degree of each state in the subproblem call graph."""
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous_limit, _RECURSION_LIMIT))
    try:
        alphabet = {character: index for index, character in enumerate(sorted(set(left + right)))}
        left_suffixes = _suffixes(left)
        right_suffixes = _suffixes(right)

        distances = tuple(
            tuple(
                binnat_to_int(
                    build(app(app(EDIT_DISTANCE, _string_to_list(left_suffix, alphabet)),
                              _string_to_list(right_suffix, alphabet)))
                )
                for right_suffix in right_suffixes
            )
            for left_suffix in left_suffixes
        )

        in_degrees = [[0] * len(right_suffixes) for _ in left_suffixes]
        for row, left_suffix in enumerate(left_suffixes):
            for column, right_suffix in enumerate(right_suffixes):
                for delta_row, delta_column in _children(left_suffix, right_suffix):
                    in_degrees[row + delta_row][column + delta_column] += 1

        distinct_states = _count_interned_states(left_suffixes, right_suffixes, alphabet)
        expected_states = len(left_suffixes) * len(right_suffixes)
        assert distinct_states == expected_states, (
            f"interpreter materialised {distinct_states} ed-call states, "
            f"expected the (m+1)(n+1) = {expected_states} of the dynamic-programming table"
        )

        return EditDistanceTrace(
            left=left,
            right=right,
            left_suffixes=left_suffixes,
            right_suffixes=right_suffixes,
            distances=distances,
            in_degrees=tuple(tuple(row) for row in in_degrees),
            distinct_states=distinct_states,
            naive_calls=_naive_call_count(left, right),
        )
    finally:
        sys.setrecursionlimit(previous_limit)


def _count_interned_states(
    left_suffixes: "tuple[str, ...]", right_suffixes: "tuple[str, ...]", alphabet: "dict[str, int]"
) -> int:
    """The number of distinct interned ``ed``-call states the interpreter holds after the full run.

    A subproblem is the interned node ``App(App(EDIT_DISTANCE, left_suffix), right_suffix)``; its arguments
    are the very suffix sub-terms of the inputs, so a node identifies a state. We force the whole term,
    then count the interned applications whose head is the ``EDIT_DISTANCE`` node and whose two arguments
    are recognised suffix nodes.
    """
    edit_distance_node = build(EDIT_DISTANCE)
    left_nodes = {id(build(_string_to_list(suffix, alphabet))): suffix for suffix in left_suffixes}
    right_nodes = {id(build(_string_to_list(suffix, alphabet))): suffix for suffix in right_suffixes}

    whole = build(app(app(EDIT_DISTANCE, _string_to_list(left_suffixes[0], alphabet)),
                      _string_to_list(right_suffixes[0], alphabet)))
    binnat_to_int(whole)  # force, so every reachable state is materialised and interned

    states = set()
    for node in list(ast_module._canonical.values()):
        if isinstance(node, App) and isinstance(node.function, App) and node.function.function is edit_distance_node:
            left_argument = node.function.argument
            right_argument = node.argument
            if id(left_argument) in left_nodes and id(right_argument) in right_nodes:
                states.add((left_nodes[id(left_argument)], right_nodes[id(right_argument)]))
    return len(states)


def _tex_suffix(suffix: str) -> str:
    return r"$\varepsilon$" if not suffix else rf"$\mathtt{{{suffix}}}$"


def _node_name(row: int, column: int) -> str:
    return f"s{row}x{column}"


def render_tikz(trace: EditDistanceTrace) -> str:
    """The ``tikzpicture`` body for the trace: the suffix-pair lattice of distinct states, each carrying its
    distance, with an arrow to every subproblem it calls and the shared states (in-degree above one)
    highlighted."""
    rows = len(trace.left_suffixes)
    columns = len(trace.right_suffixes)

    lines = [
        "% Generated by co_lambda_examples._editdistance_figure (co-lambda-editdistance-figure). Do not edit.",
        f"% Instance: left={trace.left!r}, right={trace.right!r}. Distances, the distinct-state count, and the",
        "% naive-call count are read from the interpreter; the lattice edges are the recurrence's subproblems.",
        "\\begin{tikzpicture}[",
        "  font=\\footnotesize,",
        "  state/.style={draw, rounded corners, minimum width=10mm, minimum height=8mm, align=center, inner sep=1pt},",
        "  shared/.style={draw=red!65, fill=red!10, rounded corners, minimum width=10mm, minimum height=8mm, align=center, inner sep=1pt},",
        "  axis/.style={font=\\footnotesize\\itshape},",
        "  call/.style={-Stealth, gray!55, shorten >=1pt, shorten <=1pt},",
        "]",
    ]

    for column, right_suffix in enumerate(trace.right_suffixes):
        lines.append(f"  \\node[axis] at ({column * _GRID_DX:.2f},{_GRID_DY * 0.78:.2f}) {{{_tex_suffix(right_suffix)}}};")
    for row, left_suffix in enumerate(trace.left_suffixes):
        lines.append(f"  \\node[axis] at ({-_GRID_DX * 0.82:.2f},{-row * _GRID_DY:.2f}) {{{_tex_suffix(left_suffix)}}};")

    for row in range(rows):
        for column in range(columns):
            style = "shared" if trace.in_degrees[row][column] > 1 else "state"
            position = f"({column * _GRID_DX:.2f},{-row * _GRID_DY:.2f})"
            lines.append(f"  \\node[{style}] ({_node_name(row, column)}) at {position} {{${trace.distances[row][column]}$}};")

    for row, left_suffix in enumerate(trace.left_suffixes):
        for column, right_suffix in enumerate(trace.right_suffixes):
            for delta_row, delta_column in _children(left_suffix, right_suffix):
                target = _node_name(row + delta_row, column + delta_column)
                lines.append(f"  \\draw[call] ({_node_name(row, column)}) -- ({target});")

    caption_x = (columns - 1) * _GRID_DX / 2.0
    caption_y = -(rows - 1) * _GRID_DY - _GRID_DY * 0.85
    lines.append(
        f"  \\node[anchor=north, align=center] at ({caption_x:.2f},{caption_y:.2f}) "
        f"{{\\footnotesize naive recursion: {trace.naive_calls} calls "
        f"$\\;\\Longrightarrow\\;$ tabled: {trace.distinct_states} states}};"
    )
    lines.append("\\end{tikzpicture}")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Regenerate the committed trace figure for the default tiny instance."""
    trace = build_trace(_LEFT, _RIGHT)
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(render_tikz(trace))
    print(f"wrote {_OUTPUT} ({trace.distinct_states} states, naive {trace.naive_calls} calls)")


if __name__ == "__main__":
    main()
