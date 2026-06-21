# co-lambda

The artifact for the paper *Cyclic Graphs and Memoization in Pure
$\lambda$-Calculus*. It applies **tabling**, the standard method for solving a
least-fixpoint equation, to **weak-head reduction**, giving a new operational
semantics for the pure lambda-calculus that keeps each term's standard lazy
meaning. A term that reaches finitely many distinct states comes out as a finite
graph, possibly cyclic, and the calculus stays pure: a self-referential stream
(anything `Y` builds) becomes a finite cycle with no added recursion construct,
dynamic programming shares repeated subproblems with no memoization table, and an
unproductive loop such as `Ω` is decided as `⊥`, all in finite time, where
ordinary reduction would diverge.

This repository is a uv workspace with three packages and the paper:

- [`packages/fixpoints`](packages/fixpoints) provides the least-fixpoint
  cached-property infrastructure that drives mutually recursive computations to a
  fixpoint.
- [`packages/co-lambda`](packages/co-lambda) is the interpreter: it builds terms
  with a HOAS DSL (no parser) and evaluates them by tabling, with a pluggable
  notion of when two states count as the same.
- [`packages/co-lambda-examples`](packages/co-lambda-examples) holds example
  applications written as pure lambda terms, their committed defunctionalized
  (compiled) modules, and the interpreted versus compiled benchmark.
- [`paper`](paper) is the LaTeX source whose semantics the
  interpreter realizes.

Start with the [`co-lambda` package README](packages/co-lambda) for the HOAS
DSL, the evaluator, and its tabling policies.

## Development

Run development commands through the Nix dev shell, and build distributable
artifacts as Nix packages:

```sh
# Run the test suite
direnv exec . uv run pytest

# Run the interpreted versus compiled benchmark
nix build -L .#co-lambda-benchmark-pypy

# Build the paper's supplementary material bundle
nix build -L .#co-lambda-supplementary-material
```

## License

MIT. See [`LICENSE`](LICENSE).
