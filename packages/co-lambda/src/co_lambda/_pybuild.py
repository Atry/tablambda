"""Lambda-term builders for the generic ``_pyast`` Scott encoding of a Python AST.

The compiler's target is a real Python ``ast`` Scott-encoded by ``_pyast`` (reflection-derived from the
``ast`` node classes). To let the ``COMPILE`` lambda term EMIT that generic encoding directly, this
module gives lambda-term "smart constructors", one per ``ast`` node the compiler produces, that fill in
the boilerplate fields the generic ``_pyast.decode`` reads (``decorator_list=[]``, ``returns=None``,
``ctx=Load()``, ...). Each is a thin wrapper over ``_pyast``'s own ``_ctor`` (the n-ary Scott
constructor), ``_kind`` (the field kind-tag pair), and ``_scott_list``, so the values these build are
exactly what ``_pyast.decode`` expects: ``_pyast.decode(build(<smart ctor>)) == <the ast node>``.

A node is ``_ctor(tag, fields)`` where ``tag`` is the class's index in ``_pyast.SUPPORTED`` and each
field is ``_kind(kind, payload)``; a list field's payload is a Scott list whose elements are themselves
kind-tagged fields (so a list of nodes is a Scott list of ``_field_node`` values).
"""

from __future__ import annotations

import ast

from co_lambda._codec import char_codes, church
from co_lambda._dsl import Builder, app, lam
from co_lambda._prelude import SCOTT_NIL
from co_lambda._sugar import ap, cons, map_list, one, two
from co_lambda._pyast import (
    _K_BOOL,
    _K_GENSYM,
    _K_IDENT,
    _K_INT,
    _K_LIST,
    _K_NODE,
    _K_NONE,
    _K_STR,
    _TAG,
    _ctor,
    _kind,
    _scott_list,
    encode,
)

# --- field constructors (a field is a <kind, payload> pair the decoder dispatches on) -----------


def _node(cls: "type[ast.AST]", fields: "list[Builder]") -> Builder:
    """The Scott value for an ``ast`` node of class ``cls`` with the given (kind-tagged) fields."""
    return _ctor(_TAG[cls], fields)


def field_node(child: Builder) -> Builder:
    return _kind(_K_NODE, child)


def field_list(elements: Builder) -> Builder:
    """A list field; ``elements`` is a Scott list whose items are themselves kind-tagged fields."""
    return _kind(_K_LIST, elements)


def field_int(nat: Builder) -> Builder:
    return _kind(_K_INT, nat)


def field_str(char_codes: Builder) -> Builder:
    """A string field; ``char_codes`` is a Scott list of Nat character codes."""
    return _kind(_K_STR, char_codes)


def field_ident(path: Builder) -> Builder:
    """An identifier field; ``path`` is a Scott list of Nats (an AST path). The single ``_pyast``
    decoder renders it ``v_<int>_<int>...`` for every runtime, so the lambda compiler emits only the
    path, never a rendered string."""
    return _kind(_K_IDENT, path)


def field_bool(nat: Builder) -> Builder:
    return _kind(_K_BOOL, nat)


def field_none() -> Builder:
    return _kind(_K_NONE, church(0))


def field_node_list(node_fields: Builder) -> Builder:
    """Convenience: a list field over a Scott list whose elements are already ``field_node`` values."""
    return field_list(node_fields)


# --- smart constructors, one per ast node the compiler emits -------------------------------------
# A list-valued argument is a Scott list of ALREADY kind-tagged fields (``field_node`` of each node, or
# ``field_str`` of each name), matching what the decoder's ``_K_LIST`` case feeds back to ``_decode_field``.


def py_load() -> Builder:
    return _node(ast.Load, [])


def py_store() -> Builder:
    return _node(ast.Store, [])


def py_is() -> Builder:
    return _node(ast.Is, [])


def py_name(name_field: Builder, ctx: Builder) -> Builder:
    """``ast.Name(id=<name>, ctx=<ctx>)``; ``name_field`` an already-kind-tagged name field
    (``field_str`` for a fixed name, ``field_ident`` for a variable's AST path)."""
    return _node(ast.Name, [name_field, field_node(ctx)])


def py_arg(name_field: Builder) -> Builder:
    """``ast.arg(arg=<name>, annotation=None, type_comment=None)``; ``name_field`` a name field."""
    return _node(ast.arg, [name_field, field_none(), field_none()])


def py_arguments(arg_fields: Builder) -> Builder:
    """``ast.arguments`` with only positional ``args`` populated; ``arg_fields`` a Scott list of
    ``field_node(arg)``. Order: posonlyargs, args, vararg, kwonlyargs, kw_defaults, kwarg, defaults."""
    return _node(
        ast.arguments,
        [
            field_list(SCOTT_NIL),
            field_list(arg_fields),
            field_none(),
            field_list(SCOTT_NIL),
            field_list(SCOTT_NIL),
            field_none(),
            field_list(SCOTT_NIL),
        ],
    )


def py_lambda(arg_field: Builder, body: Builder) -> Builder:
    """``lambda <arg>: <body>`` with a single positional parameter; ``arg_field`` a name field."""
    args = py_arguments(_scott_list([field_node(py_arg(arg_field))]))
    return _node(ast.Lambda, [field_node(args), field_node(body)])


def py_lambda0(body: Builder) -> Builder:
    """``lambda: <body>`` with no parameters (for a call-by-name ``Thunk(lambda: e)``)."""
    return _node(ast.Lambda, [field_node(py_arguments(SCOTT_NIL)), field_node(body)])


def py_call(func: Builder, arg_fields: Builder) -> Builder:
    """``<func>(<args...>)``; ``arg_fields`` a Scott list of ``field_node(arg)``; no keywords."""
    return _node(ast.Call, [field_node(func), field_list(arg_fields), field_list(SCOTT_NIL)])


def py_function_def(name_field: Builder, args_node: Builder, body_fields: Builder) -> Builder:
    """``def <name>(<args>): <body>`` with no decorators/returns/type comment; ``body_fields`` a Scott
    list of ``field_node(stmt)``.

    The fields are keyed by name and ordered by the RUNNING ``ast.FunctionDef._fields``, so the emitted
    node matches the host Python version: Python 3.12+ added ``type_params`` (an empty list here), which
    the generic decoder reflects, so the call-by-need target round-trips on 3.11 and on 3.12+ alike.
    """
    by_name = {
        "name": name_field,
        "args": field_node(args_node),
        "body": field_list(body_fields),
        "decorator_list": field_list(SCOTT_NIL),
        "returns": field_none(),
        "type_comment": field_none(),
        "type_params": field_list(SCOTT_NIL),
    }
    return _node(ast.FunctionDef, [by_name[name] for name in ast.FunctionDef._fields])


def py_assign(target: Builder, value: Builder) -> Builder:
    """``<target> = <value>`` with a single target. Order: targets, value, type_comment."""
    return _node(ast.Assign, [field_list(_scott_list([field_node(target)])), field_node(value), field_none()])


def py_nonlocal(name_fields: Builder) -> Builder:
    """``nonlocal <names...>``; ``name_fields`` a Scott list of ``field_str(codes)``."""
    return _node(ast.Nonlocal, [field_list(name_fields)])


def py_if(test: Builder, body_fields: Builder) -> Builder:
    """``if <test>: <body>`` with no else; ``body_fields`` a Scott list of ``field_node(stmt)``."""
    return _node(ast.If, [field_node(test), field_list(body_fields), field_list(SCOTT_NIL)])


def py_return(value: Builder) -> Builder:
    return _node(ast.Return, [field_node(value)])


def py_compare_is(left: Builder, right: Builder) -> Builder:
    """``<left> is <right>``. Order: left, ops, comparators."""
    return _node(
        ast.Compare,
        [
            field_node(left),
            field_list(_scott_list([field_node(py_is())])),
            field_list(_scott_list([field_node(right)])),
        ],
    )


def py_module(stmt_fields: Builder) -> Builder:
    """``ast.Module``; ``stmt_fields`` a Scott list of ``field_node(stmt)``. Order: body, type_ignores."""
    return _node(ast.Module, [field_list(stmt_fields), field_list(SCOTT_NIL)])


def py_constant_int(nat: Builder) -> Builder:
    """``ast.Constant(value=<int>, kind=None)`` with an integer (Nat) value."""
    return _node(ast.Constant, [field_int(nat), field_none()])


def py_subscript(value: Builder, index: Builder) -> Builder:
    """``<value>[<index>]`` (Load). Order: value, slice, ctx."""
    return _node(ast.Subscript, [field_node(value), field_node(index), field_node(py_load())])


def py_tuple(element_fields: Builder) -> Builder:
    """``(<elements...>,)`` (Load); ``element_fields`` a Scott list of ``field_node(elt)``. Order: elts, ctx."""
    return _node(ast.Tuple, [field_list(element_fields), field_node(py_load())])


# --- if-expression AST dispatch (the constructor fast path with an interpret fallback) ------------
# The compiler emits ``<body> if isinstance(n, Var) else ...`` to dispatch on a runtime lambda-AST
# node's constructor without Scott reduction (so it interns nothing). An IfExp is an EXPRESSION (it
# fits CODEGEN's expression target and runs on CPython and PyPy alike), unlike a match statement.


def py_attribute(value: Builder, attr_field: Builder) -> Builder:
    """``<value>.<attr>`` (Load); ``attr_field`` a name field (e.g. ``field_str(char_codes("index"))``).
    Order: value, attr, ctx."""
    return _node(ast.Attribute, [field_node(value), attr_field, field_node(py_load())])


def py_ifexp(test: Builder, body: Builder, orelse: Builder) -> Builder:
    """``<body> if <test> else <orelse>`` (``ast.IfExp``). Order: test, body, orelse."""
    return _node(ast.IfExp, [field_node(test), field_node(body), field_node(orelse)])


def py_isinstance(value: Builder, class_name_field: Builder) -> Builder:
    """``isinstance(<value>, <Class>)``; ``class_name_field`` a name field naming the class (``Var`` /
    ``Lam`` / ``App``, bound in the generated module header)."""
    return py_call(ex_name(field_str(char_codes("isinstance"))), two_nodes(value, ex_name(class_name_field)))


# --- emission notation: fixed-shape statement/expression/identifier helpers ----------------------
# Builder-only transcription sugar used by the CODEGEN / CODEGEN_NEED lambda terms; shapes are
# literal at the call site, parameters are Builders.


def name_gensym_field(role: Builder, quoted: Builder) -> Builder:
    """A PATH-FREE, DEPTH-FREE name field for a call-by-need memo cell/thunk, identified by its ``role``
    (cell / thunk / function) and the ``quoted`` sub-term it belongs to. The payload is interned, so the
    TABLED recursion yields the SAME node for the same (role, quoted) -- the decoder's ``_K_GENSYM`` case
    then assigns one fresh ``vg_<n>`` per distinct node, consistent across the cell's definition and uses,
    distinct across different cells. Lambda-lifted call-by-need accesses binders positionally through the
    environment, so a sub-term's compiled code does not depend on its binder depth; keying on ``quoted``
    alone (not ``(depth, quoted)``) means a sub-term shared across DIFFERENT depths compiles once, not
    once per depth (the depth-keyed scheme recompiled COMPILE's combinators once per nesting depth)."""
    return _kind(_K_GENSYM, cons(role, quoted))


def ex_name(name_field: Builder) -> Builder:
    return py_name(name_field, py_load())


def stmt(node: Builder) -> Builder:
    """Wrap a statement node as a field so it can sit in a Scott list of statements."""
    return field_node(node)


def st_func_def(name_field: Builder, parameter_fields: Builder, body_fields: Builder) -> Builder:
    arguments = py_arguments(
        map_list(lam(lambda field: field_node(py_arg(field))), parameter_fields),
    )
    return py_function_def(name_field, arguments, body_fields)


def st_assign(target_field: Builder, value: Builder) -> Builder:
    return py_assign(py_name(target_field, py_store()), value)


def st_return(value: Builder) -> Builder:
    return py_return(value)


def two_nodes(first: Builder, second: Builder) -> Builder:
    """A two-element Scott argument list of node fields."""
    return two(field_node(first), field_node(second))


# --- ClassDef / AnnAssign smart constructors for defunctionalization --------------------------------
# Mechanical boilerplate fillers for the class-based defunctionalized output. These encode no
# compilation decisions; they fill the ``ast`` fields the generic decoder expects.


def py_classdef(name_field: Builder, decorator_fields: Builder, body_fields: Builder) -> Builder:
    """``class <name>: <body>`` with decorators, no bases/keywords/type_params.

    Field order follows ``ast.ClassDef._fields`` on the running Python version.
    """
    by_name = {
        "name": name_field,
        "bases": field_list(SCOTT_NIL),
        "keywords": field_list(SCOTT_NIL),
        "body": field_list(body_fields),
        "decorator_list": field_list(decorator_fields),
        "type_params": field_list(SCOTT_NIL),
    }
    return _node(ast.ClassDef, [by_name[name] for name in ast.ClassDef._fields])


def py_annassign(target: Builder, annotation: Builder) -> Builder:
    """``<target>: <annotation>`` with no value, ``simple=1``.

    Order: target, annotation, value, simple.
    """
    return _node(ast.AnnAssign, [field_node(target), field_node(annotation), field_none(), field_int(church(1))])
