# tablambda-examples

Example applications written as pure lambda terms (HOAS) for [tablambda](../tablambda), the committed
defunctionalized (compiled) Python modules generated from them, and a benchmark comparing interpreted
versus compiled execution.

- `_editdistance.py` -- the Levenshtein edit distance as a pure lambda term.
- `_artifacts.py` -- the registry of apps and inputs, and the generator (`tablambda-defun-artifacts`)
  that defunctionalizes each into a committed module under `_generated/`.
- `_generated/` -- the committed compiled modules (one per artifact per Python version), imported by the
  benchmark so compilation never contends with the measured run.
- `_benchmark.py` -- `tablambda-defun-benchmark`: each application run interpreted vs compiled, reporting
  time, peak memory, and tabled-object count. The headline is the bootstrap (DEFUN compiling DEFUN),
  which is mandatory: there is no light subset. Results differ markedly across interpreters, so each
  writes its own fragment `../../../paper/generated/defun-benchmark-<tag>.tex`. The bootstrap needs the
  `input_quote_defun` artifact, committed for `py311` only (shared by CPython 3.11 and PyPy 3.11), so the
  full benchmark runs on those two interpreters alone (`py311`, `pypy`); on 3.12+ it fails loudly.
  Regenerate one fragment reproducibly with `nix run .#regen-defun-benchmark-<tag>`; a target exists for
  each of `py311`, `py312`, `py313`, `pypy`, but `py312`/`py313` error instead of writing a fragment.
