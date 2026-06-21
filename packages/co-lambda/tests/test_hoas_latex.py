"""The HOAS renderer: binder names from the source lambdas, named constants by identity, both styles."""

from __future__ import annotations

from co_lambda._binnat import _not
from co_lambda._dsl import app
from co_lambda._hoas_latex import MATH_STYLE, TEXT_STYLE, render
from co_lambda._prelude import IDENTITY, KESTREL


def test_math_style_renders_binders_and_application() -> None:
    assert render(IDENTITY, {}, MATH_STYLE) == "\\lambda x.\\, x"
    assert render(KESTREL, {}, MATH_STYLE) == "\\lambda x.\\, \\lambda y.\\, x"


def test_text_style_uses_ascii_lambda() -> None:
    assert render(IDENTITY, {}, TEXT_STYLE) == "\\x. x"


def test_named_constants_are_shown_by_name_not_expanded() -> None:
    # A constant in the names map is printed by name (atomic in both positions), not expanded.
    rendered = render(app(IDENTITY, IDENTITY), {id(IDENTITY): "I"}, MATH_STYLE)
    assert rendered == "I\\, I"


def test_curry_binder_names_are_preserved() -> None:
    # ``_not`` is a @curry term; its parameter name must survive (lam_named), not appear as curry's "bound".
    rendered = render(_not, {}, MATH_STYLE)
    assert "\\mathit{bit}" in rendered
    assert "bound" not in rendered
