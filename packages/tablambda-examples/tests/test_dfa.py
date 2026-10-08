"""Lexical analysis (the paper's app:dsl): the even-parity automaton, run as a fold over the
input word, accepts exactly the words with an even number of a's."""

from __future__ import annotations

from tablambda._dsl import build
from tablambda._prelude import FALSE, TRUE
from tablambda._shape import weak_head_normalize
from tablambda_examples._programs import dfa_accepts_word


def test_dfa_accepts_a_word_with_an_even_number_of_as() -> None:
    outcome = weak_head_normalize(dfa_accepts_word((True, False, True)))
    assert outcome is weak_head_normalize(build(TRUE))


def test_dfa_rejects_a_word_with_an_odd_number_of_as() -> None:
    outcome = weak_head_normalize(dfa_accepts_word((True, False)))
    assert outcome is weak_head_normalize(build(FALSE))
