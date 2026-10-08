"""Ground Datalog as a pure term (the paper's app:dsl): the least Herbrand model is the
consequence operator iterated Herbrand-base-many times from all-false, a Church-numeral
iteration, so a derivation cycle never becomes a solver cycle; a goal atom is a projection.

The instances are the paper's displayed clause sets: reachability over the cyclic graph
a -> b -> c -> a with c -> d and an isolated e, and Andersen-style points-to for
a = new o1; b = a; c = b over the objects o1, o2. The negative facts read back FALSE, not
bottom: reach(e) and pointsTo(c, o2) are atoms of the Herbrand base with no derivation.
"""

from __future__ import annotations

from tablambda._ast import Node
from tablambda._dsl import build
from tablambda._prelude import FALSE, TRUE
from tablambda._shape import weak_head_normalize
from tablambda_examples._programs import (
    DATALOG_CONJ_R,
    DATALOG_CONJ_T,
    DATALOG_REACH_C,
    DATALOG_REACH_D,
    GRAPH_REACH_D,
    GRAPH_REACH_E,
    POINTSTO_C_O1,
    POINTSTO_C_O2,
)


def _reads_true(goal: Node) -> bool:
    return weak_head_normalize(goal) is weak_head_normalize(build(TRUE))


def _reads_false(goal: Node) -> bool:
    return weak_head_normalize(goal) is weak_head_normalize(build(FALSE))


def test_reachability_through_the_cycle_derives_d_but_not_the_isolated_e() -> None:
    assert _reads_true(GRAPH_REACH_D)
    assert _reads_false(GRAPH_REACH_E)


def test_points_to_flows_o1_to_c_but_never_o2() -> None:
    assert _reads_true(POINTSTO_C_O1)
    assert _reads_false(POINTSTO_C_O2)


def test_chain_reachability_and_conjunction_examples() -> None:
    assert _reads_true(DATALOG_REACH_C)
    assert _reads_false(DATALOG_REACH_D)
    assert _reads_true(DATALOG_CONJ_T)
    assert _reads_false(DATALOG_CONJ_R)
