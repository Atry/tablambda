"""Game search (the paper's app:dsl): a transposition, the same position reached by a
different move order, is one interned node, and minimax over the and-or tree reads back the
winning Boolean."""

from __future__ import annotations

from tablambda._ast import Node
from tablambda._dsl import build
from tablambda._prelude import FALSE, TRUE
from tablambda._shape import weak_head_normalize
from tablambda_examples._programs import game_leaf, game_max, game_min, minimax


def _shared_position() -> Node:
    return game_max(game_leaf(build(FALSE)), game_leaf(build(TRUE)))


def test_transposition_is_one_interned_node() -> None:
    assert _shared_position() is _shared_position(), "interning is the transposition table"


def test_minimax_reads_back_the_winning_boolean() -> None:
    shared = _shared_position()
    tree = game_min(shared, shared)
    assert weak_head_normalize(minimax(tree)) is weak_head_normalize(build(TRUE))
