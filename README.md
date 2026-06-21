# co-lambda

The artifact for the paper *Cyclic Graphs and Memoization for Free: Solving
Coalgebraic Equations in the Pure $\lambda$-Calculus*. It reads a pure
lambda-term as a **coalgebraic equation**, a state that exposes one layer of data
over its successor states, and lets the lambda-calculus solve it by **tabled
evaluation**: it tables the states it has seen and folds the recurrence on the
decidable structural identity of the term, so a guarded cycle (anything `Y`
builds) folds into a finite cyclic graph and an unproductive cycle decides as the
meaningless leaf, both in finite time, where ordinary head reduction would
diverge.

This repository is a uv workspace with three packages and the paper:

- [`packages/fixpoints`](packages/fixpoints) provides the least-fixpoint
  cached-property infrastructure that drives mutually recursive computations to a
  fixpoint.
- [`packages/co-lambda`](packages/co-lambda) is the interpreter: it builds terms
  with a HOAS DSL (no parser) and reads them out under a pluggable position
  congruence.
- [`packages/co-lambda-examples`](packages/co-lambda-examples) holds example
  applications written as pure lambda terms, their committed defunctionalized
  (compiled) modules, and the interpreted versus compiled benchmark.
- [`papers/co-lambda`](papers/co-lambda) is the LaTeX source whose semantics the
  interpreter realizes.

Start with the [`co-lambda` package README](packages/co-lambda) for the shape
relation, the readout policies, and the four position congruences.

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
