# co_lambda

A pure lambda-calculus interpreter that applies tabling to weak-head reduction,
realizing the semantics of the paper `paper/co-lambda.tex` and depending on
`fixpoints`.

Each node's outermost constructor after weak-head reduction is a single value, a
`Var`/`Lam`/`App`/`Native` node or `BOTTOM` (no constructor), never a set.
`compute_weak_head_normal_form` is the per-node clause body, and
`Node.weak_head_normal_form` wraps it in a `fixpoint_cached_property` resolved as
a least fixpoint from `BOTTOM` upward.

Because nodes are **interned** (structurally equal nodes are one object, so
identity is a pointer test), a self-referential term reaches finitely many
distinct nodes, and a node re-entered during its own computation is caught by
that pointer test. So weak-head reduction folds a productive cycle into a finite
cyclic graph where ordinary reduction would unfold forever, and an unproductive
cycle (a re-entry that never exposes a constructor, as in `Omega` or
`Y (lambda x. x)`) stabilizes at `BOTTOM`, both in finite time. A reduction
budget (`reduction_budget`, a context variable) bounds beta-reduction, so a
genuinely non-rational term surfaces as `ReductionBudgetExceeded` instead of
hanging.

`_shape.py` exposes three readings of a term, each a least fixpoint over the
interned nodes:

- `weak_head_normalize` is the Levy-Longo reading: it fires the head spine to the
  outermost constructor and does not reduce under `lambda`.
- `head_normalize` is the Boehm reading: it also reduces under `lambda` to expose
  the head, so a `lambda` whose body has no head normal form is itself `BOTTOM`.
- `normalize_to_depth` (and `one_layer_normalize`, its `depth == 1` case) fires at
  most `depth` contractions per application position and leaves any remaining
  redex as a guarded let-stub, so every reduction terminates regardless of
  rationality.

The calculus is **pure**: the constructors are `Var`/`Lam`/`App`, with `Native`
carrying a host primitive, and no recursion binder is needed. The `Y` combinator
produces the structural repetition that interning folds, so:

- `Y (cons 0)` (the cyclic stream `r = cons 0 r`) folds to a finite cyclic graph.
- `Omega = (lambda x. x x) (lambda x. x x)` and `Y (lambda x. x)` (that is,
  `letrec x = x`) are unproductive cycles: both read out as `BOTTOM`.

## Building terms

No parser is provided. Build terms in Python with the HOAS DSL in `_dsl.py`
(`var_at`, `lam`, `lam_named`, `app`, `curry`, `build`), where Python's lexical
scope stands in for the binders; `build` compiles a `Builder` to an interned
de Bruijn AST. `_prelude.py` collects example terms (combinators, Church numerals
with Peano arithmetic, and Scott-encoded lists for cyclic data), and `_codec.py`
converts between Python values and lambda terms (`church`, `scott_list`, `quote`,
`interpret_boolean`).
