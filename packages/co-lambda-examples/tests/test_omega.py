"""The Omega artifacts are read from the interpreter, so the facts behind them are checked here.

``Omega`` must head-contract to itself (an interning identity, the re-entry the solver detects) and have a
bottom weak head normal form, decided in finite time (the check returns at all). The committed figure,
trace, and code listings the paper inputs must be exactly what the generators produce.
"""

from __future__ import annotations

from co_lambda._ast import BOTTOM
from co_lambda._shape import weak_head_normalize
from co_lambda_examples._omega import OMEGA, self_contraction, solve_omega

from co_lambda_examples import _omega_code, _omega_figure, _omega_trace


def test_omega_contracts_to_itself() -> None:
    assert self_contraction() is OMEGA  # the same interned node, so the solver re-enters it


def test_omega_is_decided_bottom_in_finite_time() -> None:
    assert weak_head_normalize(OMEGA) is BOTTOM  # returns, rather than looping forever


def test_solve_omega_checks_both_facts() -> None:
    solve_omega()  # raises if either observed fact fails


def test_committed_figure_is_current() -> None:
    assert _omega_figure._OUTPUT.read_text() == _omega_figure.render_tikz()


def test_committed_trace_is_current() -> None:
    assert _omega_trace._OUTPUT.read_text() == _omega_trace.render_trace()


def test_committed_code_is_current() -> None:
    assert _omega_code._OUTPUT.read_text() == _omega_code.code_listing()
