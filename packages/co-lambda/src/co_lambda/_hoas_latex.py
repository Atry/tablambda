"""Render a HOAS ``Builder`` term, with readable binder names and named constants, to LaTeX or to text.

``_latex.term_to_latex`` renders the built de Bruijn ``Node``: it names binders ``x, y, z, ...`` by level
and fully expands every constant, so a term built from a library (edit distance over ``Y``, the BinNat
arithmetic, the Scott list) comes out as one enormous nameless expression. Here we render the ``Builder``
instead, so a binder shows the name of the Python ``lambda`` parameter that introduced it, and a sub-term
that *is* a named library constant, recognised by object identity through a caller-supplied ``names`` map,
shows that name rather than being expanded. A definition therefore reads as itself and cross-references the
others by name. This is what generates the paper's edit-distance code listing from the source terms.

Two ``Style`` presets format the same structure differently: ``MATH_STYLE`` for inline LaTeX math (used in
the prose), ``TEXT_STYLE`` for the ASCII lambda syntax of an auto-wrapping ``lstlisting`` (the appendix
code listing, where math would overflow the line). ``names`` maps an ``id`` to the constant's *base* name
(``"eq"``, ``"Y"``, ``"ed"``); the style turns that base into the rendered token.
"""

from __future__ import annotations

import inspect

from dataclasses import dataclass
from typing import Callable, final

from co_lambda._dsl import Builder, _AppBuilder, _LamBuilder, _VarBuilder


@final
@dataclass(frozen=True, kw_only=True, slots=True)
class Style:
    """How to format the four syntactic pieces, so one renderer serves both LaTeX math and ASCII text."""

    constant: Callable[[str], str]
    binder: Callable[[str], str]
    abstraction: Callable[[str, str], str]
    application: Callable[[str, str], str]
    parenthesise: Callable[[str], str]


def _math_constant(name: str) -> str:
    return name if len(name) == 1 else f"\\mathtt{{{name}}}"


def _math_binder(name: str) -> str:
    head, _, tail = name.partition("_")
    base = head if len(head) == 1 else f"\\mathit{{{head}}}"
    return base if not tail else f"{base}_{{{tail}}}"


MATH_STYLE: Style = Style(
    constant=_math_constant,
    binder=_math_binder,
    abstraction=lambda binder, body: f"\\lambda {binder}.\\, {body}",
    application=lambda function, argument: f"{function}\\, {argument}",
    parenthesise=lambda inner: f"({inner})",
)

TEXT_STYLE: Style = Style(
    constant=lambda name: name,
    binder=lambda name: name,
    abstraction=lambda binder, body: f"\\{binder}. {body}",
    application=lambda function, argument: f"{function} {argument}",
    parenthesise=lambda inner: f"({inner})",
)


class _NamedBinder(Builder):
    """A stand-in for a bound variable while rendering: never built, only printed by its source name."""

    __slots__ = ("source_name",)

    def __init__(self, source_name: str) -> None:
        super().__init__()
        self.source_name = source_name

    def _build_at(self, depth: int):  # pragma: no cover - a rendering placeholder is never built
        raise AssertionError("a _NamedBinder is a rendering placeholder and must never be built")


def _binder_source_name(builder: _LamBuilder) -> str:
    """A lambda's bound-variable source name: its ``_binder_hint`` if set, else the Python parameter name."""
    hint = builder._binder_hint
    if hint is not None:
        return hint
    parameters = tuple(inspect.signature(builder._body).parameters)
    single_name, = parameters
    return single_name


def _fresh(name: str, scope: "tuple[str, ...]") -> str:
    """Disambiguate a binder name against those already in scope by priming, so two nested binders that
    share a source name stay distinguishable."""
    candidate = name
    while candidate in scope:
        candidate = f"{candidate}'"
    return candidate


def render(builder: Builder, names: "dict[int, str]", style: Style) -> str:
    """The rendering of ``builder``, expanding it one level (its own name, if any, is not substituted) and
    rendering every nested named constant in ``names`` by its name."""
    return _render(builder, names, style, is_root=True, scope=())


def _render(
    builder: Builder, names: "dict[int, str]", style: Style, *, is_root: bool, scope: "tuple[str, ...]"
) -> str:
    if not is_root and id(builder) in names:
        return style.constant(names[id(builder)])
    if isinstance(builder, _NamedBinder):
        return style.binder(builder.source_name)
    if isinstance(builder, _LamBuilder):
        name = _fresh(_binder_source_name(builder), scope)
        body = builder._body(_NamedBinder(name))
        rendered_body = _render(body, names, style, is_root=False, scope=(*scope, name))
        return style.abstraction(style.binder(name), rendered_body)
    if isinstance(builder, _AppBuilder):
        function = _render_function(builder._function, names, style, scope)
        argument = _render_argument(builder._argument, names, style, scope)
        return style.application(function, argument)
    if isinstance(builder, _VarBuilder):  # pragma: no cover - rendered terms introduce vars via lambdas
        raise AssertionError("a free _VarBuilder reached the renderer; rendered terms must be closed")
    raise TypeError(f"cannot render {builder!r}")


def _is_atom(builder: Builder, names: "dict[int, str]") -> bool:
    """An atom needs no parentheses in argument position: a bound variable or a named constant."""
    return isinstance(builder, (_NamedBinder, _VarBuilder)) or id(builder) in names


def _render_function(
    builder: Builder, names: "dict[int, str]", style: Style, scope: "tuple[str, ...]"
) -> str:
    # A lambda shown expanded must be parenthesised in function position; a name or an application is bare.
    inner = _render(builder, names, style, is_root=False, scope=scope)
    if isinstance(builder, _LamBuilder) and id(builder) not in names:
        return style.parenthesise(inner)
    return inner


def _render_argument(
    builder: Builder, names: "dict[int, str]", style: Style, scope: "tuple[str, ...]"
) -> str:
    inner = _render(builder, names, style, is_root=False, scope=scope)
    return inner if _is_atom(builder, names) else style.parenthesise(inner)
