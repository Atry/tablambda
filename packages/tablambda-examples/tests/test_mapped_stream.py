"""Map over the cyclic stream (the paper's app:dsl): the ordinary map, with nothing
cycle-aware in it, folds ``Y (cons 0)`` into the finite circle of ones."""

from __future__ import annotations

from tablambda._pyast import _church_to_int
from tablambda._shape import weak_head_normalize
from tablambda_examples._cyclic_zeros import cons_cell
from tablambda_examples._programs import CYCLIC_ONES


def test_map_over_the_cyclic_stream_folds_to_a_cyclic_stream_of_ones() -> None:
    cell = weak_head_normalize(CYCLIC_ONES)
    pair = cons_cell(cell)
    assert pair is not None, "map succ over the stream must expose a cons cell"
    head, tail = pair
    assert _church_to_int(head) == 1
    assert weak_head_normalize(tail) is cell, "the tail's layer is the cell itself, the back edge"
