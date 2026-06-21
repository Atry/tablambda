# co-lambda-examples

Example applications written as pure lambda terms (HOAS) for [co-lambda](../co-lambda), the committed
defunctionalized (compiled) Python modules generated from them, and a benchmark comparing interpreted
versus compiled execution.

- `_editdistance.py` -- the Levenshtein edit distance as a pure lambda term.
- `_artifacts.py` -- the registry of apps and inputs, and the generator (`co-lambda-defun-artifacts`)
  that defunctionalizes each into a committed module under `_generated/`.
- `_generated/` -- the committed compiled modules (one per artifact per Python version), imported by the
  benchmark so compilation never contends with the measured run.
- `_benchmark.py` -- `co-lambda-defun-benchmark`: each application run interpreted vs compiled, reporting
  time, peak memory, and tabled-object count. The headline is the bootstrap (DEFUN compiling DEFUN).
