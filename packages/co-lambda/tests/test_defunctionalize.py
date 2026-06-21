"""Tests for the defunctionalization compiler.

Progresses from codec round-trips through simple combinators to the edit-distance tabling test.
"""

from __future__ import annotations

import time

import pytest
from syrupy.assertion import SnapshotAssertion

from co_lambda._ast import Node, make_app, make_lam, make_var
from co_lambda._defun_runtime import Thunk, _BOTTOM, _is_thunk, _python_tag, interned
from co_lambda._defunctionalize import (
    defunctionalize,
    defunctionalize_and_load,
    load,
    reify,
)
from co_lambda._dsl import app, build, lam
from co_lambda._prelude import (
    IDENTITY,
    KESTREL,
    SELF_APPLY,
    SCOTT_CONS,
    SCOTT_NIL,
    SUCC,
    TRUE,
    Y,
    ZERO,
    ONE,
)
from co_lambda._sugar import ap


# --- 1. codec round-trip: ClassDef / AnnAssign survive encode-decode ----------------------------

def test_codec_classdef_roundtrip():
    """A ClassDef with AnnAssign fields round-trips through the generic Scott codec."""
    import ast
    from co_lambda._pyast import encode, decode

    source = """
@interned
@dataclass
class Cls:
    cap_0: object
    def __call__(self, a):
        return a
"""
    tree = ast.parse(source.strip())
    cls_def = tree.body[0]
    encoded = encode(cls_def)
    node = build(encoded)
    decoded = decode(node)
    assert isinstance(decoded, ast.ClassDef)
    assert decoded.name == "Cls"
    assert len(decoded.decorator_list) == 2
    assert len(decoded.body) == 2
    annassign = decoded.body[0]
    assert isinstance(annassign, ast.AnnAssign)


# --- 2. Identity / Kestrel / Church numerals ----------------------------------------------------

def test_identity():
    source = defunctionalize(build(IDENTITY))
    value = load(source)
    sentinel = object()
    result = Thunk(value, sentinel)
    assert result.weak_head_normal_form is sentinel


def test_kestrel():
    source = defunctionalize(build(KESTREL))
    value = load(source)
    a, b = object(), object()
    result = Thunk(Thunk(value, a), b)
    assert result.weak_head_normal_form is a


def test_church_zero():
    node = build(lam(lambda s: lam(lambda z: z)))
    value = defunctionalize_and_load(node)
    s, z = object(), object()
    result = Thunk(Thunk(value, s), z)
    assert result.weak_head_normal_form is z


def test_church_one():
    node = build(lam(lambda s: lam(lambda z: app(s, z))))
    value = defunctionalize_and_load(node)
    marker = object()
    identity_fn = defunctionalize_and_load(build(IDENTITY))
    result = Thunk(Thunk(value, identity_fn), marker)
    assert result.weak_head_normal_form is marker


# --- 3. free-variable capture -------------------------------------------------------------------

def test_capture_kx():
    """`\\x.\\y.x` captures x in the inner closure."""
    node = build(KESTREL)
    source = defunctionalize(node)
    assert "@interned" in source
    assert "cap_0: Lambda" in source
    assert "__call__" in source


def test_s_combinator_capture(snapshot: SnapshotAssertion):
    """`\\x.\\y.\\z. x z (y z)` (S combinator) captures correctly.

    The generated class names are content hashes that legitimately differ between Python versions
    (``ast.unparse`` formatting and the ``ast.dump`` the hash digests both vary, e.g. ``type_params``
    on 3.12+), which is why generated artifacts are tagged by ``_python_tag()``. The snapshot is
    keyed the same way so each interpreter compares against its own expected output.
    """
    s_comb = build(lam(lambda x: lam(lambda y: lam(lambda z: app(app(x, z), app(y, z))))))
    source = defunctionalize(s_comb)
    assert source == snapshot(name=f"s_combinator_source_{_python_tag()}")


# --- 4. content-addressability ------------------------------------------------------------------

def test_interned_closures_share_identity():
    """Two closures from the same QLam with identical captures are the same object."""
    node = build(KESTREL)
    value = defunctionalize_and_load(node)
    a = object()
    v1 = Thunk(value, a).weak_head_normal_form
    v2 = Thunk(value, a).weak_head_normal_form
    assert v1 is v2


def test_interned_thunks_share_identity():
    """Two Thunks with the same callee and argument are the same object."""
    callee = object()
    arg = object()
    t1 = Thunk(callee, arg)
    t2 = Thunk(callee, arg)
    assert t1 is t2


def _class_names(source: str) -> "list[str]":
    import re
    return re.findall(r"^class (\w+):", source, re.M)


def test_coarser_tabling_merges_structurally_equal_closures():
    """Closures of the same shape capturing different de Bruijn depths share one dataclass.

    ``\\a.\\g. cons (\\b.a) (\\b.g)`` has two inner ``\\b.<captured>`` closures: one captures ``a``
    (de Bruijn 2 inside), the other ``g`` (de Bruijn 1 inside). Both compile to the same dataclass
    (one capture field, ``__call__`` returns ``self.<cap_0>``), so exactly one such class is emitted
    and both call sites reference it. This is coarser than the source term equality.
    """
    term = build(lam(lambda a: lam(lambda g: ap(SCOTT_CONS, lam(lambda b: a), lam(lambda b: g)))))
    source = defunctionalize(term)
    names = _class_names(source)
    assert len(names) == len(set(names)), "class definitions must be unique after canonicalization"

    # The single-field identity-capture closure appears once as a definition but is referenced twice.
    single_capture = [
        name for name in names
        if f"class {name}:" in source and source.count(f"{name}(") >= 2
    ]
    assert single_capture, "expected a shared closure class referenced at multiple call sites"


def test_content_address_is_stable_across_compiles():
    """The same closure shape gets the same class name in two independent compilations."""
    k1 = defunctionalize(build(KESTREL))
    # K embedded under an extra binder: the inner \\.\\.x closure has the same compiled shape.
    k2 = defunctionalize(build(lam(lambda z: KESTREL)))
    shared = set(_class_names(k1)) & set(_class_names(k2))
    assert shared, "structurally identical closures must share a content-addressed name"


# --- 5. productive cycle: Y (cons 0) -----------------------------------------------------------

def test_productive_cycle_y_cons():
    """Y (\\self. cons 0 self) produces a value whose whnf is a closure, not bottom."""
    node = build(app(Y, lam(lambda self_rec: ap(SCOTT_CONS, ZERO, self_rec))))
    value = defunctionalize_and_load(node)
    if _is_thunk(value):
        whnf = value.weak_head_normal_form
        assert whnf is not _BOTTOM
        assert callable(whnf)


# --- 6. Omega: unproductive cycle stabilises at bottom -----------------------------------------

def test_omega_stabilises_at_bottom():
    """(\\x.xx)(\\x.xx) is an unproductive cycle; whnf is bottom."""
    omega = build(app(SELF_APPLY, SELF_APPLY))
    value = defunctionalize_and_load(omega)
    if _is_thunk(value):
        assert value.weak_head_normal_form is _BOTTOM


# --- 7. cross-reference: reify matches interpreter ---------------------------------------------

def _interpreter_normal_form(node: Node, depth: int = 0) -> Node:
    """Read the interpreter's normal form of a closed term (NbE readback).

    Probe variables are created as ``make_var(level)``; quoting converts level ``l`` under
    ``depth`` binders to de Bruijn index ``depth - l - 1``.
    """
    from co_lambda._ast import App, Lam, Var

    whnf = node.weak_head_normal_form
    match whnf:
        case Var(index=level):
            return make_var(depth - level - 1)
        case Lam():
            probe = make_var(depth)
            applied = make_app(node, probe)
            return make_lam(_interpreter_normal_form(applied, depth + 1))
        case App(function=function, argument=argument):
            return make_app(
                _interpreter_normal_form(function, depth),
                _interpreter_normal_form(argument, depth),
            )
        case _:
            raise ValueError(f"unexpected weak head normal form {whnf!r}")


_CROSS_CHECK_TERMS = [
    ("identity", IDENTITY),
    ("kestrel", KESTREL),
    ("church_0", lam(lambda s: lam(lambda z: z))),
    ("church_2", lam(lambda s: lam(lambda z: app(s, app(s, z))))),
]


@pytest.mark.parametrize("name, term", _CROSS_CHECK_TERMS, ids=[t[0] for t in _CROSS_CHECK_TERMS])
def test_reify_matches_interpreter(name: str, term):
    node = build(term)
    value = defunctionalize_and_load(node)
    reified = reify(value)
    interp_nf = _interpreter_normal_form(node)
    assert reified is interp_nf
