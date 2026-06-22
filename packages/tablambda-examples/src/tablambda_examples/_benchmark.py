"""Benchmark applications run interpreted vs run compiled (defunctionalized).

The matrix is ``2 x apps x inputs``: every application is run on every input both by the tabled
interpreter and by its compiled (defunctionalized) form. The compiled app AND the compiled inputs are
IMPORTED from committed pre-compiled modules under ``_generated`` (see ``_artifacts``); the compiled cell
compiles nothing in-process, so compilation never contends with the measured run.

* ``edit-distance`` -- the Levenshtein function ``EDIT_DISTANCE``; an input is a pair of strings.
  Interpreted: force ``EDIT_DISTANCE a b``. Compiled: import the function and the two list inputs, apply,
  force.
* ``DEFUN`` -- the compiler; an input is the source program ``quote(P)`` to compile. Interpreted: run
  ``DEFUN`` in the interpreter. Compiled: import the committed compiled compiler and the compiled quoted
  input, apply, read back the emitted source. The decisive input is ``P = DEFUN``: the bootstrap.

Per cell three metrics are compared (ratio = interpreter / compiled, > 1 means the compiled form wins):
wall-clock execution time, peak resident memory (RSS), and the number of TABLED objects
materialized (interpreter: interned lambda ``Node`` count; compiled: interned ``Thunk`` and closure
instances). Each cell runs in a fresh subprocess (clean interner, absolute counts); the interpreted and
compiled results are checked equal. The bootstrap is heavy (minutes, gigabytes). The result is
written to ``paper/generated/defun-benchmark.tex``.
``tablambda-defun-benchmark`` runs ``main``; ``--measure <approach> <app> <input>`` is the worker.
"""

from __future__ import annotations

import gc
import hashlib
import importlib
import json
import resource
import subprocess
import sys
import time

from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
_OUTPUT = _REPO_ROOT / "paper" / "generated" / "defun-benchmark.tex"

_RECURSION_LIMIT = 1_000_000

# (display name, app, input key, heavy). Heavy cells are part of the generated fragment.
_CELLS = [
    ("edit-distance kitten/sitting", "editdistance", "kitten:sitting", False),
    ("edit-distance intention/execution", "editdistance", "intention:execution", False),
    ("DEFUN on identity", "defun", "identity", False),
    ("DEFUN on S", "defun", "S", False),
    ("DEFUN on DEFUN (bootstrap)", "defun", "defun", True),
]

# Compiled input artifacts to import per cell input key.
_EDIT_INPUTS = {
    "kitten:sitting": ("input_kitten", "input_sitting"),
    "intention:execution": ("input_intention", "input_execution"),
}
_DEFUN_INPUTS = {
    "identity": "input_quote_identity",
    "S": "input_quote_s",
    "defun": "input_quote_defun",
}


@dataclass(frozen=True, kw_only=True, slots=True)
class Cell:
    """One measured (approach, app, input) subprocess: execution time, peak heap, tabled count, digest."""

    seconds: float
    peak_mb: float
    tabled: int
    digest: str


@dataclass(frozen=True, kw_only=True, slots=True)
class ComparisonRow:
    """One (app, input) run both ways, with the compiled-vs-interpreter ratios (>1 means compiled wins)."""

    name: str
    interpreter: Cell
    compiled: Cell

    @property
    def speedup(self) -> float:
        return self.interpreter.seconds / self.compiled.seconds if self.compiled.seconds else 0.0

    @property
    def memory_ratio(self) -> float:
        return self.interpreter.peak_mb / self.compiled.peak_mb if self.compiled.peak_mb else 0.0

    @property
    def tabled_ratio(self) -> float:
        return self.interpreter.tabled / self.compiled.tabled if self.compiled.tabled else 0.0


# --- the per-cell worker (run in a fresh subprocess) --------------------------------------------


def _all_defun_tabled() -> int:
    """The total interned-instance count across every defunctionalized class (``__intern_pool__``)."""
    total = 0
    for obj in gc.get_objects():
        if isinstance(obj, type):
            pool = obj.__dict__.get("__intern_pool__")
            if pool is not None:
                total += len(pool)
    return total


def _import_compiled(artifact_name: str) -> object:
    """Import a committed artifact module and return its ``compiled`` value (no in-process compilation)."""
    from tablambda_examples._artifacts import module_dotted_name

    return importlib.import_module(module_dotted_name(artifact_name)).compiled


def _measure(run, count_tabled) -> "tuple[float, float, int]":
    """Time ``run`` (already-imported/constructed inputs) and read this fresh process's peak RSS.

    Each cell is its own subprocess, so peak RSS (``ru_maxrss``) is the cell's own peak; using it
    instead of ``tracemalloc`` avoids the per-allocation overhead that makes the gigabyte-scale
    bootstrap impractical. Time is the core ``run`` region; memory is the whole-process peak.
    """
    start = time.perf_counter()
    run()
    seconds = time.perf_counter() - start
    peak_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0  # ru_maxrss is KB on Linux
    return seconds, peak_mb, count_tabled()


def _measure_editdistance(approach: str, input_key: str) -> "tuple[float, float, int, str]":
    import tablambda._ast as ast_module
    from tablambda._dsl import app, build
    from tablambda._pyast import binnat_to_int

    left, right = input_key.split(":")
    result: "list[int]" = []
    if approach == "interpreter":
        from tablambda_examples._artifacts import _string_term
        from tablambda_examples._editdistance import EDIT_DISTANCE

        node = build(app(app(EDIT_DISTANCE, _string_term(left)), _string_term(right)))  # setup
        seconds, peak_mb, tabled = _measure(
            lambda: result.append(binnat_to_int(node)), lambda: len(ast_module._canonical)
        )
        return seconds, peak_mb, tabled, str(result[0])

    from tablambda._defun_runtime import Thunk

    function = _import_compiled("editdistance")  # the compiled app, imported (no compilation)
    left_name, right_name = _EDIT_INPUTS[input_key]
    compiled_left = _import_compiled(left_name)
    compiled_right = _import_compiled(right_name)

    def run() -> None:
        applied = Thunk(Thunk(function, compiled_left), compiled_right).weak_head_normal_form
        result.append(binnat_to_int(applied))

    seconds, peak_mb, tabled = _measure(run, _all_defun_tabled)
    return seconds, peak_mb, tabled, str(result[0])


def _defun_program(input_key: str) -> object:
    from tablambda._defun_codegen import DEFUN
    from tablambda._dsl import app, build, lam
    from tablambda._prelude import IDENTITY

    if input_key == "defun":
        return build(DEFUN)
    if input_key == "identity":
        return build(IDENTITY)
    if input_key == "S":
        return build(lam(lambda x: lam(lambda y: lam(lambda z: app(app(x, z), app(y, z))))))
    raise ValueError(f"unknown DEFUN input {input_key!r}")


def _measure_defun(approach: str, input_key: str) -> "tuple[float, float, int, str]":
    import ast as python_ast

    import tablambda._ast as ast_module

    source: "list[str]" = []
    if approach == "interpreter":
        from tablambda._defunctionalize import defunctionalize

        node = _defun_program(input_key)  # setup
        seconds, peak_mb, tabled = _measure(
            lambda: source.append(defunctionalize(node)), lambda: len(ast_module._canonical)
        )
        return seconds, peak_mb, tabled, hashlib.sha256(source[0].encode()).hexdigest()

    from tablambda._defunctionalize import (
        _canonicalize_classes,
        _memoized_decode_defun,
        _reset_defun_gensym,
        decode_defun,
    )
    from tablambda._defun_runtime import Thunk, _BOTTOM

    engine = _import_compiled("compiler")  # the committed compiled compiler, imported
    quoted_input = _import_compiled(_DEFUN_INPUTS[input_key])

    def run() -> None:
        result = Thunk(engine, quoted_input).weak_head_normal_form
        assert result is not _BOTTOM, "the compiled compiler did not produce a module"
        _reset_defun_gensym()
        with _memoized_decode_defun():
            decoded = decode_defun(result)
        assert isinstance(decoded, python_ast.Module)
        canonical = _canonicalize_classes(decoded)
        source.append(python_ast.unparse(python_ast.fix_missing_locations(canonical)))

    seconds, peak_mb, tabled = _measure(run, _all_defun_tabled)
    return seconds, peak_mb, tabled, hashlib.sha256(source[0].encode()).hexdigest()


def _worker(approach: str, app: str, input_key: str) -> None:
    """Run one cell and print its measurement as JSON (the subprocess entry)."""
    sys.setrecursionlimit(max(sys.getrecursionlimit(), _RECURSION_LIMIT))
    if app == "editdistance":
        seconds, peak_mb, tabled, digest = _measure_editdistance(approach, input_key)
    elif app == "defun":
        seconds, peak_mb, tabled, digest = _measure_defun(approach, input_key)
    else:
        raise ValueError(f"unknown app {app!r}")
    print(json.dumps({"seconds": seconds, "peak_mb": peak_mb, "tabled": tabled, "digest": digest}))


# --- the parent: spawn cells, collect, render ----------------------------------------------------


def _spawn(approach: str, app: str, input_key: str) -> Cell:
    completed = subprocess.run(
        [sys.executable, "-m", "tablambda_examples._benchmark", "--measure", approach, app, input_key],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    return Cell(
        seconds=payload["seconds"], peak_mb=payload["peak_mb"],
        tabled=payload["tabled"], digest=payload["digest"],
    )


def comparison_rows() -> "list[ComparisonRow]":
    """Run every cell both ways (each in its own subprocess) and return the comparison rows."""
    rows: "list[ComparisonRow]" = []
    for name, app, input_key, heavy in _CELLS:
        interpreter = _spawn("interpreter", app, input_key)
        compiled = _spawn("compiled", app, input_key)
        assert interpreter.digest == compiled.digest, (
            f"cell {app}:{input_key}: interpreted and compiled results differ"
        )
        rows.append(ComparisonRow(name=name, interpreter=interpreter, compiled=compiled))
    return rows


def _tabular(rows: "list[ComparisonRow]") -> str:
    header = (
        "App / input "
        "& \\shortstack[r]{Interp\\\\time} & \\shortstack[r]{Defun\\\\time} & Speedup "
        "& \\shortstack[r]{Interp\\\\mem} & \\shortstack[r]{Defun\\\\mem} & \\shortstack[r]{Mem\\\\ratio} "
        "& \\shortstack[r]{Interp\\\\tabled} & \\shortstack[r]{Defun\\\\tabled} "
        "& \\shortstack[r]{Tabled\\\\ratio} \\\\"
    )
    body = [
        "  "
        + " & ".join([
            row.name,
            f"{row.interpreter.seconds:.3f}", f"{row.compiled.seconds:.3f}", f"{row.speedup:.2f}",
            f"{row.interpreter.peak_mb:.0f}", f"{row.compiled.peak_mb:.0f}", f"{row.memory_ratio:.2f}",
            str(row.interpreter.tabled), str(row.compiled.tabled), f"{row.tabled_ratio:.2f}",
        ])
        + " \\\\"
        for row in rows
    ]
    return "\n".join([
        "\\begin{tabular}{lrrrrrrrrr}", "\\hline", header, "\\hline", *body, "\\hline", "\\end{tabular}",
    ])


def benchmark_fragment() -> str:
    """The committed LaTeX fragment: the interpreted-vs-compiled comparison tabular and a header."""
    rows = comparison_rows()
    parts = [
        "% Generated by tablambda_examples._benchmark (tablambda-defun-benchmark). Do not edit.",
        "% Each application run interpreted vs compiled (defunctionalized, imported pre-compiled). Time (s)",
        "% and peak RSS (MB) are a measured snapshot; tabled-object counts (interned nodes vs interned",
        "% Thunks+closures) and the ratio columns (interp/defun) are the comparison. A ratio > 1 means the",
        "% compiled form wins.",
        _tabular(rows),
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    """Console entry. ``--measure <approach> <app> <input>`` is the per-cell worker; otherwise spawn the
    matrix, print it, and write the LaTeX fragment."""
    if len(sys.argv) >= 5 and sys.argv[1] == "--measure":
        _worker(sys.argv[2], sys.argv[3], sys.argv[4])
        return

    rows = comparison_rows()
    print(
        f"{'app / input':<36}  {'interp_s':>9} {'defun_s':>9} {'x':>5}  "
        f"{'i_MB':>7} {'d_MB':>7}  {'i_tab':>9} {'d_tab':>9} {'ratio':>5}"
    )
    for row in rows:
        print(
            f"{row.name:<36}  {row.interpreter.seconds:>9.3f} {row.compiled.seconds:>9.3f} "
            f"{row.speedup:>5.2f}  {row.interpreter.peak_mb:>7.0f} {row.compiled.peak_mb:>7.0f}  "
            f"{row.interpreter.tabled:>9} {row.compiled.tabled:>9} {row.tabled_ratio:>5.2f}"
        )
    _OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT.write_text(benchmark_fragment())
    print(f"wrote {_OUTPUT}")


if __name__ == "__main__":
    main()
