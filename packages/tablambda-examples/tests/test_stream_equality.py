"""Coinductive stream equality as a guarded verdict stream (the paper's app:dsl).

Equirecursive equality is a greatest fixpoint (revisit means equal) while the evaluator
computes least fixpoints; guarding the comparison closes the gap. ``eqS`` exposes one
per-level verdict before recursing, so on two behaviorally equal cyclic streams the solver
folds the verdict stream into a finite cycle of a single TRUE (the tail's layer is the cell
itself), and on streams that differ the first verdict is FALSE at the first disagreement.
Reading "no FALSE occurs" off the finite verdict graph is the standard metalanguage
observation.
"""

from __future__ import annotations

from tablambda._dsl import build
from tablambda._prelude import FALSE, TRUE
from tablambda._shape import weak_head_normalize
from tablambda_examples._cyclic_zeros import STREAM, cons_cell
from tablambda_examples._programs import (
    CYCLIC_ONES_DIRECT,
    CYCLIC_ZEROS_ETA,
    stream_equality_verdicts,
)


def test_equal_cyclic_streams_fold_to_the_finite_cycle_of_true() -> None:
    verdicts = stream_equality_verdicts(STREAM, CYCLIC_ZEROS_ETA)
    cell = weak_head_normalize(verdicts)
    pair = cons_cell(cell)
    assert pair is not None, "the verdict stream must expose a cons cell"
    head, tail = pair
    assert weak_head_normalize(head) is weak_head_normalize(build(TRUE))
    assert weak_head_normalize(tail) is cell, (
        "one TRUE verdict on a self-loop: the whole comparison is this finite cycle"
    )


def test_differing_streams_expose_a_false_verdict_at_the_first_disagreement() -> None:
    verdicts = stream_equality_verdicts(STREAM, CYCLIC_ONES_DIRECT)
    cell = weak_head_normalize(verdicts)
    pair = cons_cell(cell)
    assert pair is not None, "the verdict stream must expose a cons cell"
    head, _tail = pair
    assert weak_head_normalize(head) is weak_head_normalize(build(FALSE))
