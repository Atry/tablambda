# co_lambda

A pure lambda-calculus interpreter that applies tabling to weak-head reduction,
realizing the semantics of the paper `paper/co-lambda.tex` and depending on
`fixpoints`.

The interpreter tables the states it has already seen, so a term that reaches
finitely many distinct states comes out as a finite graph, possibly cyclic, while
the calculus stays pure and the result is independent of reduction order. A
self-referential stream (anything `Y` builds) folds into a finite cycle with no
added recursion construct, dynamic programming shares its repeated subproblems
with no memoization table, and an unproductive loop such as `Omega` is decided as
the meaningless value, all in finite time, where ordinary reduction would
diverge.

No parser is provided: terms are built directly in Python and a small prelude
collects the usual combinators, Church numerals, and Scott-encoded lists.
