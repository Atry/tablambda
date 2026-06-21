"""A Higher-Order Abstract Syntax surface, compiled to the first-order de Bruijn AST.

Object-language binders are written with Python ``lambda``, so terms read isomorphically to
the lambda-calculus, and Python's lexical scope is the implicit symbol table (no name
environment, no capture handling). The calculus is pure (``Var``/``Lam``/``App``); cyclic and
recursive data are written with the ``Y`` combinator (no recursion binder is needed, since
interning folds the structurally-repeating positions a ``Y`` recursion produces). The Python
lambdas run once at build time; the result is a pure first-order tree.

A ``Builder`` is a HOAS term: an abstract base whose subclasses (``_VarBuilder``, ``_LamBuilder``,
``_AppBuilder``) each know how to produce their de Bruijn node at a given binder depth. Calling a
builder is object-language application (``f(x, y)`` is ``((f x) y)``); the depth-indexed node is
read with ``.at(depth)`` (or ``build`` at depth zero).
"""

from __future__ import annotations

import inspect

from abc import ABC, abstractmethod
from typing import Callable

from co_lambda._ast import Node, make_app, make_lam, make_var


class Builder(ABC):
    """A HOAS term: given the current binder depth, produce a de Bruijn node.

    ``.at(depth)`` memoises the node by binder depth. A builder is a pure function of the binder
    depth, so reusing the same builder object in several places (a shared subterm) yields the same
    node at a given depth. Caching by depth makes a shared-builder DAG build in time linear in its
    distinct nodes instead of unfolding it into a tree: ``build`` reaches each child builder per
    occurrence, so without the cache a builder reused in ``n`` places is re-run ``n`` times. The
    result nodes are interned regardless; this shares the construction work too.
    """

    __slots__ = ("_node_by_depth",)

    def __init__(self) -> None:
        self._node_by_depth: dict[int, Node] = {}

    @abstractmethod
    def _build_at(self, depth: int) -> Node:
        """Produce this term's de Bruijn node at ``depth`` (uncached); implemented per subclass."""

    def at(self, depth: int) -> Node:
        """This HOAS term's de Bruijn node at the given binder depth (memoised)."""
        node = self._node_by_depth.get(depth)
        if node is None:
            node = self._build_at(depth)
            self._node_by_depth[depth] = node
        return node

    def __call__(self, *arguments: "Builder") -> "Builder":
        """Object-language application, left-folded: ``f(x, y, z)`` is ``((f x) y) z``."""
        result: Builder = self
        for argument in arguments:
            result = _AppBuilder(result, argument)
        return result


class _VarBuilder(Builder):
    """A bound variable, named by the binder level it refers to (turned into a de Bruijn index by
    subtracting from the current depth)."""

    __slots__ = ("_level",)

    def __init__(self, level: int) -> None:
        super().__init__()
        self._level = level

    def _build_at(self, depth: int) -> Node:
        return make_var(depth - self._level - 1)


class _LamBuilder(Builder):
    """An abstraction: a Python function from the bound-variable builder to the body builder.

    ``_binder_hint`` is the readable name of the bound variable when it is known up front (``lam_named``,
    used by ``curry`` to keep a decorated function's parameter names); ``None`` means a renderer should
    recover the name from the Python lambda's own parameter. It never affects the built node.
    """

    __slots__ = ("_body", "_binder_hint")

    def __init__(self, body: "Callable[[Builder], Builder]", binder_hint: "str | None") -> None:
        super().__init__()
        self._body = body
        self._binder_hint = binder_hint

    def _build_at(self, depth: int) -> Node:
        return make_lam(self._body(_VarBuilder(depth)).at(depth + 1))


class _AppBuilder(Builder):
    """An application of one builder to another."""

    __slots__ = ("_function", "_argument")

    def __init__(self, function: Builder, argument: Builder) -> None:
        super().__init__()
        self._function = function
        self._argument = argument

    def _build_at(self, depth: int) -> Node:
        return make_app(self._function.at(depth), self._argument.at(depth))


def var_at(level: int) -> Builder:
    return _VarBuilder(level)


def lam(body: "Callable[[Builder], Builder]") -> Builder:
    return _LamBuilder(body, None)


def lam_named(binder_name: str, body: "Callable[[Builder], Builder]") -> Builder:
    """``lam`` with the bound variable's readable name given explicitly, for when the body callable does
    not carry it (a ``curry`` wrapper); the name is for rendering only and never affects the built node."""
    return _LamBuilder(body, binder_name)


def app(function: Builder, argument: Builder) -> Builder:
    return _AppBuilder(function, argument)


def curry(body: "Callable[..., Builder]") -> Builder:
    """Expand an N-argument Python function into a curried HOAS lambda.

    ``curry(lambda a, b, c: e)`` is ``lam(lambda a: lam(lambda b: lam(lambda c: e)))``: the
    function's parameter count (read with ``inspect``) fixes the binder arity, and each parameter
    is the ``Builder`` for a bound variable. A zero-argument ``body`` builds no binder and returns
    ``body()`` directly. This is sugar for the nested ``lam`` chains that multi-argument terms need.
    """
    parameter_names = tuple(inspect.signature(body).parameters)
    arity = len(parameter_names)

    def collect(arguments: "list[Builder]") -> Builder:
        if len(arguments) == arity:
            return body(*arguments)
        return lam_named(parameter_names[len(arguments)], lambda bound: collect([*arguments, bound]))

    return collect([])


def build(term: Builder) -> Node:
    """Finalize a HOAS term into a de Bruijn ``Node``."""
    return term.at(0)
