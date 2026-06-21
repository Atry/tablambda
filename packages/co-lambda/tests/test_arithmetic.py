"""Church-numeral arithmetic, run on the interpreter.

Each case observes a Church numeral as an int (or a Church boolean as a bool) through the
interpreter's weak-head reduction.
"""

from __future__ import annotations

import math

import pytest

from co_lambda._ast import Var, make_app, make_var
from co_lambda._codec import church
from co_lambda._dsl import build, app
from co_lambda._pyast import _church_to_int
from co_lambda._prelude import EXP, FACTORIAL, FIBONACCI, IS_ZERO, MULT, PLUS, PRED, SUCC

_TRUE_MARKER = 7_000_001
_FALSE_MARKER = 7_000_002


def _church(term) -> int:
    return _church_to_int(build(term))


def _boolean(term) -> bool:
    node = build(term)
    applied = make_app(make_app(node, make_var(_TRUE_MARKER)), make_var(_FALSE_MARKER))
    whnf = applied.weak_head_normal_form
    match whnf:
        case Var(index=index) if index == _TRUE_MARKER:
            return True
        case Var(index=index) if index == _FALSE_MARKER:
            return False
        case _:
            raise ValueError(f"not a Church boolean: {whnf!r}")


@pytest.mark.parametrize("n", [0, 1, 3])
def test_church_numeral(n: int) -> None:
    assert _church(church(n)) == n


@pytest.mark.parametrize("n", [0, 1, 2, 5])
def test_succ(n: int) -> None:
    assert _church(app(SUCC, church(n))) == n + 1


@pytest.mark.parametrize("m, n", [(0, 0), (0, 3), (2, 3), (4, 1)])
def test_plus(m: int, n: int) -> None:
    assert _church(app(app(PLUS, church(m)), church(n))) == m + n


@pytest.mark.parametrize("m, n", [(0, 4), (2, 3), (3, 3)])
def test_mult(m: int, n: int) -> None:
    assert _church(app(app(MULT, church(m)), church(n))) == m * n


@pytest.mark.parametrize("m, n", [(2, 2), (2, 3), (3, 2)])
def test_exp(m: int, n: int) -> None:
    assert _church(app(app(EXP, church(m)), church(n))) == m**n


@pytest.mark.parametrize("n", [1, 2, 5])
def test_pred(n: int) -> None:
    assert _church(app(PRED, church(n))) == n - 1


def test_is_zero() -> None:
    assert _boolean(app(IS_ZERO, church(0))) is True
    assert _boolean(app(IS_ZERO, church(3))) is False


@pytest.mark.parametrize("n", [0, 1, 2, 3, 4])
def test_factorial(n: int) -> None:
    assert _church(app(FACTORIAL, church(n))) == math.factorial(n)


@pytest.mark.parametrize("n, fib", [(0, 0), (1, 1), (2, 1), (3, 2), (4, 3), (5, 5)])
def test_fibonacci(n: int, fib: int) -> None:
    assert _church(app(FIBONACCI, church(n))) == fib
