"""The defunctionalization compiler, written in the pure lambda calculus.

The source is a quoted lambda term (Scott values over ``QVar i`` / ``QLam body`` / ``QApp f a``,
de Bruijn). ``DEFUN`` is a pure lambda term that maps the quoted source to a Scott-encoded
``ast.Module`` of ``@interned @dataclass`` closure classes and a root expression. Each ``QLam``
becomes a dataclass whose fields are its free variables and whose ``__call__`` is the compiled
beta reduction; each ``QApp`` becomes ``Thunk(callee, argument)``.

This module is pure lambda calculus (one of the four strictly separated kinds: codec / sugar /
runtime / pure-lambda source): every top-level binding is a ``Builder``, written through the
``_dsl``/``_sugar``/``_pybuild`` notation with ``_codec`` literal renderings.
"""

from __future__ import annotations

from co_lambda._binnat import BIN_EQUAL, BIN_IS_ZERO, BIN_PRED, BIN_SUCC, BIN_ZERO
from co_lambda._codec import char_codes, int_to_binnat
from co_lambda._dsl import Builder, app, lam
from co_lambda._prelude import FALSE, SCOTT_NIL, TRUE, Y
from co_lambda._pybuild import (
    ex_name,
    field_node,
    field_str,
    name_gensym_field,
    py_annassign,
    py_attribute,
    py_call,
    py_classdef,
    py_module,
    st_assign,
    st_func_def,
    st_return,
    stmt,
    two_nodes,
)
from co_lambda._sugar import ap, cons, let, one, pair, pair_first, pair_second, two


# --- BinNat index comparison utilities --------------------------------------------------------
# De Bruijn indices are BinNat-encoded (O(log n) per index). Comparison uses the _binnat operation
# which is O(log n), vs O(n) for Church numeral arithmetic.

_EQ_IDX: Builder = BIN_EQUAL


# --- BinNat list utilities --------------------------------------------------------------------

DECREMENT_POSITIVE: Builder = app(Y, lam(lambda self_rec: lam(lambda xs: app(
    app(
        xs,
        lam(lambda head: lam(lambda tail: app(
            app(app(BIN_IS_ZERO, head),
                app(self_rec, tail)),
            lam(lambda c: lam(lambda n: app(app(c, app(BIN_PRED, head)), app(self_rec, tail)))),
        ))),
    ),
    SCOTT_NIL,
))))

LIST_APPEND: Builder = app(Y, lam(lambda self_rec: lam(lambda xs: lam(lambda ys: app(
    app(
        xs,
        lam(lambda h: lam(lambda t: lam(lambda c: lam(lambda n: app(app(c, h), ap(self_rec, t, ys)))))),
    ),
    ys,
)))))

# Membership of a BinNat index in a BinNat list, as a Scott boolean.
MEMBER_IDX: Builder = app(Y, lam(lambda self_rec: lam(lambda x: lam(lambda xs: app(
    app(
        xs,
        lam(lambda head: lam(lambda tail: app(
            app(ap(_EQ_IDX, x, head), TRUE),
            ap(self_rec, x, tail),
        ))),
    ),
    FALSE,
)))))

# Order-preserving union: ``xs`` followed by each element of ``ys`` not already present, deduplicating
# by FIRST OCCURRENCE. Unlike a sorted merge, this keeps the order in which indices first appear, so a
# capture's field position follows its first use in the compiled body rather than its de Bruijn value.
ORDERED_UNION: Builder = app(Y, lam(lambda self_rec: lam(lambda xs: lam(lambda ys: app(
    app(
        ys,
        lam(lambda head: lam(lambda tail: app(
            app(ap(MEMBER_IDX, head, xs),
                ap(self_rec, xs, tail)),
            ap(self_rec, ap(LIST_APPEND, xs, one(head)), tail),
        ))),
    ),
    xs,
)))))


# --- FREE_VARS: free de Bruijn indices of a quoted term, in first-occurrence order --------------
# A QApp emits ``Thunk(callee, argument)`` (callee subtree before argument subtree), so the free
# variables are collected callee-first; a capture's field position then follows the order in which it
# is first dereferenced in the compiled ``__call__`` body. PROCESS_FREE_VARS, MAKE_BODY_ENV, and
# MAP_FREE_VARS_TO_ARGS all derive from this one list, so fields, body-env lookups, and constructor
# arguments share the order automatically; content addressing then merges closures whose bodies use
# their captures in the same order even when the captured de Bruijn indices differ.

FREE_VARS: Builder = app(Y, lam(lambda self_rec: lam(lambda quoted: ap(
    quoted,
    lam(lambda index: lam(lambda c: lam(lambda n: app(app(c, index), SCOTT_NIL)))),
    lam(lambda body: app(DECREMENT_POSITIVE, app(self_rec, body))),
    lam(lambda function: lam(lambda argument: ap(
        ORDERED_UNION, app(self_rec, function), app(self_rec, argument),
    ))),
))))


# --- Name constants for emitted code -----------------------------------------------------------

_INTERNED_CODES: Builder = char_codes("interned")
_LAMBDA_CODES: Builder = char_codes("Lambda")
_SELF_CODES: Builder = char_codes("self")
_A_CODES: Builder = char_codes("a")
_THUNK_CODES: Builder = char_codes("Thunk")
_COMPILED_CODES: Builder = char_codes("compiled")
_CALL_CODES: Builder = char_codes("__call__")

_INTERNED_NAME: Builder = ex_name(field_str(_INTERNED_CODES))
_LAMBDA_NAME: Builder = ex_name(field_str(_LAMBDA_CODES))
_SELF_NAME: Builder = ex_name(field_str(_SELF_CODES))
_THUNK_NAME: Builder = ex_name(field_str(_THUNK_CODES))

_A_FIELD: Builder = field_str(_A_CODES)
_SELF_FIELD: Builder = field_str(_SELF_CODES)

_KIND_CLASS: Builder = int_to_binnat(10)
_KIND_CAPTURE: Builder = int_to_binnat(11)

_DECORATOR_LIST: Builder = one(field_node(_INTERNED_NAME))


# --- PROCESS_FREE_VARS: build capture fields and the body-env lookup list together --------------
# This processes the free-var list once and produces a pair:
#   (annassign_stmts,   -- Scott list of stmt(AnnAssign) fields for the class body
#    field_name_list)   -- Scott list of (debruijn_index, field_name) pairs for body-env lookup
#
# Capture field names are content-addressable by POSITION ALONE, not by the owning QLam: a class's
# fields live in the class namespace, so the i-th capture is named identically in every class. This
# is what makes two closures of the same shape (same arity and same compiled body) but capturing
# variables at different de Bruijn depths compile to the SAME dataclass: their capture fields, their
# body env, and hence their whole class body are byte-identical (a coarser equivalence than the
# source QLam's node identity). The class NAME is then content-addressed by the compiled body (see
# the QLam case below), so identical bodies share one class.
#
# The capture name's payload is the EXACT SAME interned node in both the annotation and the body-env
# lookup because it is built once per free variable and threaded through both uses.

PROCESS_FREE_VARS: Builder = app(Y, lam(lambda self_rec: lam(
    lambda position: lam(lambda free_vars: app(
        app(
            free_vars,
            lam(lambda head: lam(lambda tail: let(
                name_gensym_field(_KIND_CAPTURE, position),
                lambda cap_name: let(
                    ap(self_rec, app(BIN_SUCC, position), tail),
                    lambda rest: pair(
                        cons(
                            stmt(py_annassign(ex_name(cap_name), _LAMBDA_NAME)),
                            pair_first(rest),
                        ),
                        cons(
                            pair(head, cap_name),
                            pair_second(rest),
                        ),
                    ),
                ),
            ))),
        ),
        pair(SCOTT_NIL, SCOTT_NIL),
    )))))


# LOOKUP_FIELD_NAME: index -> field_name_list -> field_name
# Finds the field name for a given de Bruijn index in the list of (index, name) pairs.
LOOKUP_FIELD_NAME: Builder = app(Y, lam(lambda self_rec: lam(
    lambda index: lam(lambda name_list: app(
        app(
            name_list,
            lam(lambda head_pair: lam(lambda tail: app(
                head_pair,
                lam(lambda stored_index: lam(lambda field_name: app(
                    app(ap(_EQ_IDX, index, stored_index), field_name),
                    ap(self_rec, index, tail),
                ))),
            ))),
        ),
        field_str(char_codes("LOOKUP_FAILED")),
    )))))


# MAKE_BODY_ENV: field_name_list -> (de Bruijn index -> Python expression)
# index 0 -> Name("a")
# index k > 0 -> self.<field_name for k-1 in field_name_list>
MAKE_BODY_ENV: Builder = lam(lambda field_name_list: lam(lambda index: app(
    app(app(BIN_IS_ZERO, index),
        ex_name(_A_FIELD)),
    py_attribute(
        _SELF_NAME,
        ap(LOOKUP_FIELD_NAME, app(BIN_PRED, index), field_name_list),
    ),
)))

# MAP_FREE_VARS_TO_ARGS: free_vars -> env -> Scott list of field_node(env(idx))
MAP_FREE_VARS_TO_ARGS: Builder = app(Y, lam(lambda self_rec: lam(
    lambda free_vars: lam(lambda env: app(
        app(
            free_vars,
            lam(lambda head: lam(lambda tail: cons(
                field_node(app(env, head)),
                ap(self_rec, tail, env),
            ))),
        ),
        SCOTT_NIL,
    )))))


# --- DEFUN_REC: the core compilation recursion --------------------------------------------------

_DEFUN_REC: Builder = app(Y, lam(lambda self_rec: lam(lambda quoted: ap(
    quoted,

    # QVar index: no defs, value = env(index)
    lam(lambda index: pair(
        lam(lambda rest: rest),
        lam(lambda env: app(env, index)),
    )),

    # QLam body: class definition + constructor call. Capture fields are positional (self.cap_p),
    # so two QLams of the same shape that capture variables at different de Bruijn depths produce
    # byte-identical class bodies. The provisional class name keys on the source QLam node (giving
    # deterministic names within one compile); the boundary's ``_canonicalize_classes`` then renames
    # every class by the Merkle hash of its COMPILED body, merging the byte-identical ones. This is
    # the coarser, compiled-form content addressing.
    lam(lambda body: let(
        app(self_rec, body),
        lambda compiled_body: let(
            app(FREE_VARS, quoted),
            lambda free_vars: let(
                ap(PROCESS_FREE_VARS, BIN_ZERO, free_vars),
                lambda processed: let(
                    pair_first(processed),
                    lambda annassigns: let(
                        pair_second(processed),
                        lambda field_name_list: pair(
                            # defs: this class + body's defs
                            lam(lambda rest: cons(
                                stmt(py_classdef(
                                    name_gensym_field(_KIND_CLASS, quoted),
                                    _DECORATOR_LIST,
                                    ap(
                                        LIST_APPEND,
                                        annassigns,
                                        one(stmt(st_func_def(
                                            field_str(_CALL_CODES),
                                            two(_SELF_FIELD, _A_FIELD),
                                            one(stmt(st_return(ap(
                                                pair_second(compiled_body),
                                                app(MAKE_BODY_ENV, field_name_list),
                                            )))),
                                        ))),
                                    ),
                                )),
                                ap(pair_first(compiled_body), rest),
                            )),

                            # value: ClassName(env(fv_0), env(fv_1), ...)
                            lam(lambda env: py_call(
                                ex_name(name_gensym_field(_KIND_CLASS, quoted)),
                                ap(MAP_FREE_VARS_TO_ARGS, free_vars, env),
                            )),
                        ),
                    ),
                ),
            ),
        ),
    )),

    # QApp f a: Thunk(callee, argument); defs = f's defs ++ a's defs
    lam(lambda function: lam(lambda argument: let(
        app(self_rec, function),
        lambda compiled_f: let(
            app(self_rec, argument),
            lambda compiled_a: pair(
                lam(lambda rest: ap(
                    pair_first(compiled_f),
                    ap(pair_first(compiled_a), rest),
                )),
                lam(lambda env: py_call(
                    _THUNK_NAME,
                    two_nodes(
                        ap(pair_second(compiled_f), env),
                        ap(pair_second(compiled_a), env),
                    ),
                )),
            ),
        ),
    ))),
))))


# --- DEFUN: top-level entry point ---------------------------------------------------------------

DEFUN: Builder = lam(lambda quoted: let(
    app(_DEFUN_REC, quoted),
    lambda root: py_module(ap(
        pair_first(root),
        one(stmt(st_assign(
            field_str(_COMPILED_CODES),
            ap(
                pair_second(root),
                lam(lambda _index: ex_name(field_str(char_codes("UNREACHABLE")))),
            ),
        ))),
    )),
))
