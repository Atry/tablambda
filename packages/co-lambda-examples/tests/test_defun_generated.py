"""The committed compiled artifacts must load, self-host faithfully, and the benchmark must run.

The example apps and inputs are defunctionalized to committed modules under ``_generated`` (see
``co_lambda_examples._artifacts``). A light test imports the compiled compiler and checks it loads; the
heavy tests (regenerate-and-diff, self-host faithfulness) are gated behind ``FOL_REGEN_DEFUN=1`` (a
dedicated gate, distinct from the deprecated multistage bootstrap's ``FOL_REGEN_HEAVY``).
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest

from co_lambda._defunctionalize import compile_with_defun, defun_compiler_source, defunctionalize
from co_lambda._dsl import app, build, lam
from co_lambda._prelude import IDENTITY, KESTREL

from co_lambda_examples._artifacts import module_dotted_name


_COMPILER_MODULE = module_dotted_name("compiler")


def test_committed_compiled_compiler_loads() -> None:
    """The committed compiled compiler imports and binds a callable ``compiled`` engine."""
    module = importlib.import_module(_COMPILER_MODULE)
    assert callable(module.compiled)


@pytest.mark.skipif(
    os.environ.get("FOL_REGEN_DEFUN") != "1",
    reason="self-compiling DEFUN takes minutes; set FOL_REGEN_DEFUN=1 to run",
)
def test_committed_compiled_compiler_matches_source() -> None:
    """The committed compiler artifact is exactly what ``defun_compiler_source`` produces now (no drift)."""
    committed = importlib.import_module(_COMPILER_MODULE)
    committed_file = committed.__file__
    assert committed_file is not None, f"module {_COMPILER_MODULE} has no __file__"
    committed_text = Path(committed_file).read_text()
    assert committed_text == defun_compiler_source()


@pytest.mark.skipif(
    os.environ.get("FOL_REGEN_DEFUN") != "1",
    reason="running the self-hosted compiler takes minutes; set FOL_REGEN_DEFUN=1 to run",
)
def test_self_hosted_compiler_is_faithful() -> None:
    """The compiled compiler compiles sample programs exactly like the in-process compiler."""
    engine = importlib.import_module(_COMPILER_MODULE).compiled
    for term in (IDENTITY, KESTREL, lam(lambda s: lam(lambda z: app(s, app(s, z))))):
        node = build(term)
        assert compile_with_defun(engine, node) == defunctionalize(node)


def test_defun_benchmark_metrics_are_stable(snapshot) -> None:
    """The benchmark's DETERMINISTIC metrics (tabled-object counts) do not drift, and per cell the
    interpreted and compiled results agree.

    Time and memory are a measured snapshot and excluded here; the interned-object counts capture the
    coarser, compiled-form tabling, which must stay stable. Running each cell spawns subprocesses, so
    this covers only the light (non-bootstrap) cells.
    """
    from co_lambda_examples._benchmark import comparison_rows

    deterministic = {
        row.name: {
            "interpreter_tabled": row.interpreter.tabled,
            "compiled_tabled": row.compiled.tabled,
            "results_agree": row.interpreter.digest == row.compiled.digest,
        }
        for row in comparison_rows(include_heavy=False)
    }
    assert deterministic == snapshot(name="defun_benchmark_metrics")


def test_committed_compiler_examples_matches_generator() -> None:
    """The committed ``compiler-examples.tex`` is exactly what the examples generator produces now."""
    from co_lambda_examples._examples import _LATEX_OUTPUT, compiler_examples_fragment

    assert _LATEX_OUTPUT.read_text() == compiler_examples_fragment()


def test_defun_benchmark_fragment_renders() -> None:
    """The benchmark renders a LaTeX tabular fragment (the committed paper input)."""
    from co_lambda_examples._benchmark import benchmark_fragment

    fragment = benchmark_fragment(include_heavy=False)
    assert "\\begin{tabular}" in fragment
    assert "\\shortstack[r]{Tabled\\\\ratio}" in fragment


def _edit_distance_reference(left: str, right: str) -> int:
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


def test_defun_edit_distance_matches_reference() -> None:
    """The defunctionalized edit distance agrees with the textbook reference (tabling preserved)."""
    import sys

    from co_lambda._defunctionalize import defunctionalize, load, reify
    from co_lambda._pyast import binnat_to_int

    from co_lambda_examples._editdistance import edit_distance_term

    left, right = "cat", "cot"
    value = load(defunctionalize(edit_distance_term(left, right)))
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous, 100_000))
    try:
        result = binnat_to_int(reify(value))
    finally:
        sys.setrecursionlimit(previous)
    assert result == _edit_distance_reference(left, right)
