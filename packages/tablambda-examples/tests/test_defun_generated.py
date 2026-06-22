"""The committed compiled artifacts must load, self-host faithfully, and the benchmark must run.

The example apps and inputs are defunctionalized to committed modules under ``_generated`` (see
``tablambda_examples._artifacts``). A light test imports the compiled compiler and checks it loads; the
heavier tests are marked ``slow``.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from tablambda._defunctionalize import compile_with_defun, defun_compiler_source, defunctionalize
from tablambda._dsl import app, build, lam
from tablambda._prelude import IDENTITY, KESTREL

from tablambda_examples._artifacts import module_dotted_name


_COMPILER_MODULE = module_dotted_name("compiler")

# The committed _generated artifacts and compiler-examples.tex are produced under CPython 3.11 and
# reproduced byte for byte only by it and PyPy 3.11 (which shares its ast.unparse). Tests that depend on
# reproducing them are parametrized over the four interpreters so each one's expected status is declared:
# a case runs only under its own interpreter (the rest skip via skipif), and CPython 3.12/3.13 do not
# reproduce the CPython 3.11 artifacts, so there those tests are expected failures.
_RUNNING_INTERPRETER = (
    "pypy" if sys.implementation.name == "pypy"
    else f"py{sys.version_info.major}{sys.version_info.minor}"
)

_PY311_ARTIFACT_INTERPRETERS = [
    pytest.param(
        "py311",
        marks=pytest.mark.skipif(
            _RUNNING_INTERPRETER != "py311",
            reason=f"runs under py311; current interpreter is {_RUNNING_INTERPRETER}",
        ),
    ),
    pytest.param(
        "py312",
        marks=[
            pytest.mark.skipif(
                _RUNNING_INTERPRETER != "py312",
                reason=f"runs under py312; current interpreter is {_RUNNING_INTERPRETER}",
            ),
            pytest.mark.xfail(
                reason="CPython 3.12 does not reproduce the committed CPython 3.11 artifacts (the deep "
                "bootstrap input exceeds its recursion cap, and ast.unparse formats the compiled "
                "modules differently)",
                strict=True,
            ),
        ],
    ),
    pytest.param(
        "py313",
        marks=[
            pytest.mark.skipif(
                _RUNNING_INTERPRETER != "py313",
                reason=f"runs under py313; current interpreter is {_RUNNING_INTERPRETER}",
            ),
            pytest.mark.xfail(
                reason="CPython 3.13 does not reproduce the committed CPython 3.11 artifacts (the deep "
                "bootstrap input exceeds its recursion cap, and ast.unparse formats the compiled "
                "modules differently)",
                strict=True,
            ),
        ],
    ),
    pytest.param(
        "pypy",
        marks=pytest.mark.skipif(
            _RUNNING_INTERPRETER != "pypy",
            reason=f"runs under pypy; current interpreter is {_RUNNING_INTERPRETER}",
        ),
    ),
]


def test_committed_compiled_compiler_loads() -> None:
    """The committed compiled compiler imports and binds a callable ``compiled`` engine."""
    module = importlib.import_module(_COMPILER_MODULE)
    assert callable(module.compiled)


@pytest.mark.slow
def test_committed_compiled_compiler_matches_source() -> None:
    """The committed compiler artifact is exactly what ``defun_compiler_source`` produces now (no drift)."""
    committed = importlib.import_module(_COMPILER_MODULE)
    committed_file = committed.__file__
    assert committed_file is not None, f"module {_COMPILER_MODULE} has no __file__"
    committed_text = Path(committed_file).read_text()
    assert committed_text == defun_compiler_source()


@pytest.mark.slow
def test_self_hosted_compiler_is_faithful() -> None:
    """The compiled compiler compiles sample programs exactly like the in-process compiler."""
    engine = importlib.import_module(_COMPILER_MODULE).compiled
    for term in (IDENTITY, KESTREL, lam(lambda s: lam(lambda z: app(s, app(s, z))))):
        node = build(term)
        assert compile_with_defun(engine, node) == defunctionalize(node)


@pytest.mark.slow
@pytest.mark.parametrize("interpreter", _PY311_ARTIFACT_INTERPRETERS)
def test_defun_benchmark_metrics_are_stable(interpreter: str, snapshot) -> None:
    """The benchmark's DETERMINISTIC metrics (tabled-object counts) do not drift, and per cell the
    interpreted and compiled results agree.

    Time and memory are a measured snapshot and excluded here; the interned-object counts capture the
    coarser, compiled-form tabling, which must stay stable. The benchmark runs every cell including the
    heavy bootstrap (minutes); the counts are identical on CPython 3.11 and PyPy 3.11 (shared py311
    artifacts), so one snapshot covers both.
    """
    assert interpreter == _RUNNING_INTERPRETER

    from tablambda_examples._benchmark import comparison_rows

    deterministic = {
        row.name: {
            "interpreter_tabled": row.interpreter.tabled,
            "compiled_tabled": row.compiled.tabled,
            "results_agree": row.interpreter.digest == row.compiled.digest,
        }
        for row in comparison_rows()
    }
    assert deterministic == snapshot(name="defun_benchmark_metrics")


@pytest.mark.parametrize("interpreter", _PY311_ARTIFACT_INTERPRETERS)
def test_committed_compiler_examples_matches_generator(interpreter: str) -> None:
    """The committed ``compiler-examples.tex`` is exactly what the examples generator produces now.

    The generator unparses the compiled modules, whose formatting and content-addressed class names
    differ across Python versions, so the committed fragment is the CPython 3.11 form; only CPython 3.11
    and PyPy 3.11 reproduce it byte for byte.
    """
    assert interpreter == _RUNNING_INTERPRETER

    from tablambda_examples._examples import _LATEX_OUTPUT, compiler_examples_fragment

    assert _LATEX_OUTPUT.read_text() == compiler_examples_fragment()


@pytest.mark.slow
@pytest.mark.parametrize("interpreter", _PY311_ARTIFACT_INTERPRETERS)
def test_defun_benchmark_fragment_renders(interpreter: str) -> None:
    """The full benchmark runs and renders a LaTeX tabular fragment (the committed paper input).

    This measures every cell including the heavy bootstrap (minutes); on 3.12/3.13 the bootstrap input
    is absent and it fails loudly, an expected failure declared in the parametrization.
    """
    assert interpreter == _RUNNING_INTERPRETER

    from tablambda_examples._benchmark import benchmark_fragment

    fragment = benchmark_fragment()
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

    from tablambda._defunctionalize import defunctionalize, load
    from tablambda._pyast import binnat_to_int

    from tablambda_examples._editdistance import edit_distance_term

    left, right = "cat", "cot"
    value = load(defunctionalize(edit_distance_term(left, right)))
    previous = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous, 100_000))
    try:
        result = binnat_to_int(value)
    finally:
        sys.setrecursionlimit(previous)
    assert result == _edit_distance_reference(left, right)
