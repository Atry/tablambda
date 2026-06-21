"""The defunctionalization boundary: quote, compile, decode, canonicalize, load.

Thin Python layer analogous to ``_specialize`` but for the defunctionalization target. The lambda
compiler ``DEFUN`` produces the Scott-encoded ``ast.Module``; this module quotes the input, runs
the compiler in the interpreter, decodes the Scott AST to a real ``ast.Module``, deduplicates
class definitions by node identity (``memoized_decode``), renames every class by the Merkle hash of
its COMPILED body (``_canonicalize_classes``), and unparses to source. ``load`` execs the source
with the runtime globals (``Thunk``, ``interned``, ``dataclass``) and returns the ``compiled``
value.

Content addressing happens on the compiled dataclass, not the source lambda term. Two source
closures of the same shape that capture variables at different de Bruijn depths compile to the same
dataclass (same arity, byte-identical ``__call__`` body over positional capture fields), so the
boundary collapses them to one class. This is coarser than the source's term equality and makes the
generated code smaller and more reusable.
"""

from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
from typing import TypeVar

from co_lambda._ast import Node
from co_lambda._codec import quote_binnat
from co_lambda._defun_codegen import DEFUN
from co_lambda._defun_runtime import Thunk, _BOTTOM, _is_thunk, interned, run_in_large_stack

_AstNode = TypeVar("_AstNode", bound=ast.AST)
from co_lambda._dsl import app, build
from co_lambda._pyast import SUPPORTED, _ARITY, _reset_gensym, decode, memoized_decode


class _RenameClasses(ast.NodeTransformer):
    """Rewrite ``ast.Name`` references to class names according to ``mapping``."""

    def __init__(self, mapping: "dict[str, str]") -> None:
        self._mapping = mapping

    def visit_Name(self, node: ast.Name) -> ast.Name:
        renamed = self._mapping.get(node.id)
        if renamed is not None:
            return ast.copy_location(ast.Name(id=renamed, ctx=node.ctx), node)
        return node


def _rename_copy(node: _AstNode, mapping: "dict[str, str]") -> _AstNode:
    """A deep copy of ``node`` with class-name references rewritten per ``mapping``."""
    renamed = _RenameClasses(mapping).visit(copy.deepcopy(node))
    assert isinstance(renamed, type(node)), (
        f"_RenameClasses must preserve node type {type(node).__name__}, got {type(renamed).__name__}"
    )
    return renamed


class _RenameFields(ast.NodeTransformer):
    """Rewrite a class's capture-field names (AnnAssign targets and ``self.<field>`` accesses)."""

    def __init__(self, mapping: "dict[str, str]") -> None:
        self._mapping = mapping

    def visit_Name(self, node: ast.Name) -> ast.Name:
        renamed = self._mapping.get(node.id)
        if renamed is not None:
            return ast.copy_location(ast.Name(id=renamed, ctx=node.ctx), node)
        return node

    def visit_Attribute(self, node: ast.Attribute) -> ast.Attribute:
        self.generic_visit(node)
        renamed = self._mapping.get(node.attr)
        if renamed is not None:
            node.attr = renamed
        return node


def _canonicalize_fields(classdef: ast.ClassDef) -> ast.ClassDef:
    """Rename a class's capture fields to positional ``cap_<i>`` names (in definition order)."""
    field_names = [
        statement.target.id
        for statement in classdef.body
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
    ]
    mapping = {name: f"cap_{position}" for position, name in enumerate(field_names)}
    renamed = _RenameFields(mapping).visit(copy.deepcopy(classdef))
    assert isinstance(renamed, ast.ClassDef)
    return renamed


def _canonicalize_classes(module: ast.Module) -> ast.Module:
    """Rename every closure class by a content hash of its COMPILED dataclass and drop duplicates.

    Capture fields are first renamed positionally (``cap_0``, ``cap_1``, ...). The content hash of a
    class is then the Merkle hash of its (field-canonicalized) body with references to other classes
    replaced by THEIR content hashes (computed bottom-up over the acyclic class-reference DAG) and the
    class's own name replaced by a fixed placeholder. Two classes with identical compiled bodies hash
    equal and collapse to one. Definitions are emitted sorted by name, so the output is stable under
    local source edits and identical between the in-process and self-hosted compilers.
    """
    classdefs: "dict[str, ast.ClassDef]" = {}
    others: "list[ast.stmt]" = []
    for statement in module.body:
        if isinstance(statement, ast.ClassDef):
            field_canonical = _canonicalize_fields(statement)
            kept = classdefs.get(field_canonical.name)
            if kept is not None:
                assert ast.dump(kept) == ast.dump(field_canonical), (
                    f"provisional class {field_canonical.name!r} has two non-identical definitions"
                )
                continue
            classdefs[field_canonical.name] = field_canonical
        else:
            others.append(statement)
    provisional = set(classdefs)

    def referenced(classdef: ast.ClassDef) -> "set[str]":
        return {n.id for n in ast.walk(classdef) if isinstance(n, ast.Name) and n.id in provisional}

    canonical: "dict[str, str]" = {}
    in_progress: "set[str]" = set()

    def canonical_name(name: str) -> str:
        cached = canonical.get(name)
        if cached is not None:
            return cached
        assert name not in in_progress, f"class reference cycle through {name!r}"
        in_progress.add(name)
        classdef = classdefs[name]
        mapping = {reference: canonical_name(reference) for reference in referenced(classdef)}
        mapping[name] = "_SELF_"
        key_node = _rename_copy(classdef, mapping)
        assert isinstance(key_node, ast.ClassDef)
        key_node.name = "_SELF_"
        digest = hashlib.sha256(ast.dump(key_node).encode()).digest()[:8]
        result = "vg_" + digest.hex()
        in_progress.discard(name)
        canonical[name] = result
        return result

    for name in classdefs:
        canonical_name(name)

    global_mapping = {name: canonical[name] for name in provisional}
    deduped: "dict[str, ast.ClassDef]" = {}
    for name, classdef in classdefs.items():
        renamed = _rename_copy(classdef, global_mapping)
        assert isinstance(renamed, ast.ClassDef)
        renamed.name = canonical[name]
        deduped[renamed.name] = renamed

    sorted_defs: "list[ast.stmt]" = [deduped[key] for key in sorted(deduped)]
    new_others = [_rename_copy(statement, global_mapping) for statement in others]
    module.body = sorted_defs + new_others
    return module


# --- Direct defun decoder: decode Scott-encoded AST from defunctionalized values -----------------
# Mirrors ``_pyast.decode`` but operates on defun values (Thunk + closures) instead of interpreter
# Nodes, eliminating the expensive ``reify`` NbE round-trip in the self-hosted compilation path.


class _TagMarker:
    """Callable marker for Scott constructor extraction. When the Scott value selects this handler,
    it calls ``__call__`` once per field, accumulating the field values."""

    __slots__ = ("tag", "fields")

    def __init__(self, tag: int) -> None:
        self.tag = tag
        self.fields: list[object] = []

    def __call__(self, argument: object) -> "_TagMarker":
        self.fields.append(argument)
        return self


class _ChurchApp:
    """Marker node in a Church numeral spine: successor applied to predecessor."""

    __slots__ = ("argument",)

    def __init__(self, argument: object) -> None:
        self.argument = argument


class _ChurchSucc:
    """Callable marker for Church numeral successor."""

    __slots__ = ()

    def __call__(self, argument: object) -> _ChurchApp:
        return _ChurchApp(argument)


_CHURCH_SUCC_DEFUN = _ChurchSucc()
_CHURCH_ZERO_DEFUN = object()

_church_int_cache: "dict[int, int]" = {}
_defun_gensym_ids: "dict[int, str]" = {}
_defun_gensym_counter: int = 0
_defun_decode_memo: "dict[int, ast.AST] | None" = None


def _reset_defun_gensym() -> None:
    _church_int_cache.clear()
    _defun_gensym_ids.clear()
    global _defun_gensym_counter
    _defun_gensym_counter = 0


@contextlib.contextmanager
def _memoized_decode_defun():
    global _defun_decode_memo
    assert _defun_decode_memo is None, "memoized decode_defun does not nest"
    _defun_decode_memo = {}
    try:
        yield
    finally:
        _defun_decode_memo = None


def _force_defun(value: object) -> object:
    if _is_thunk(value):
        whnf = value.weak_head_normal_form
        assert whnf is not _BOTTOM, "hit bottom while forcing defun value"
        return whnf
    return value


def _extract_defun(value: object, arities: "tuple[int, ...]") -> "tuple[int, list[object]]":
    current = _force_defun(value)
    for tag in range(len(arities)):
        assert callable(current), f"expected callable during extraction, got {type(current).__name__}"
        result = current(_TagMarker(tag))
        current = _force_defun(result)
    assert isinstance(current, _TagMarker), (
        f"expected _TagMarker after extraction, got {type(current).__name__}"
    )
    return current.tag, current.fields


def _church_to_int_defun(value: object) -> int:
    key = id(value)
    cached = _church_int_cache.get(key)
    if cached is not None:
        return cached
    current = _force_defun(value)
    assert callable(current), f"church spine head must be callable, got {type(current).__name__}"
    current = current(_CHURCH_SUCC_DEFUN)
    current = _force_defun(current)
    assert callable(current), f"church spine successor result must be callable, got {type(current).__name__}"
    current = current(_CHURCH_ZERO_DEFUN)
    current = _force_defun(current)
    count = 0
    while isinstance(current, _ChurchApp):
        count += 1
        current = _force_defun(current.argument)
    assert current is _CHURCH_ZERO_DEFUN, "church spine did not end at zero marker"
    _church_int_cache[key] = count
    return count


def _decode_scott_list_defun(value: object) -> "list[object]":
    items: "list[object]" = []
    current = value
    while True:
        tag, fields = _extract_defun(current, (2, 0))
        if tag == 1:
            return items
        assert tag == 0, f"expected cons (0) or nil (1), got {tag}"
        items.append(fields[0])
        current = fields[1]


def _gensym_name_defun(payload: object) -> str:
    global _defun_gensym_counter
    key = id(payload)
    existing = _defun_gensym_ids.get(key)
    if existing is not None:
        return existing
    name = f"vg_{_defun_gensym_counter:016x}"
    _defun_gensym_counter += 1
    _defun_gensym_ids[key] = name
    return name


def _decode_field_defun(value: object) -> object:
    _, fields = _extract_defun(value, (2,))
    kind_value, payload = fields
    kind = _church_to_int_defun(kind_value)
    match kind:
        case 0:
            return decode_defun(payload)
        case 1:
            return [_decode_field_defun(item) for item in _decode_scott_list_defun(payload)]
        case 2:
            return _church_to_int_defun(payload)
        case 3:
            return "".join(chr(_church_to_int_defun(code)) for code in _decode_scott_list_defun(payload))
        case 5:
            return None
        case 7:
            return _gensym_name_defun(payload)
        case _:
            raise ValueError(f"defun decode: unsupported field kind {kind}")


def decode_defun(value: object) -> ast.AST:
    """Decode a Scott-encoded AST directly from defunctionalized values (Thunks + closures).

    Skips the ``reify`` NbE round-trip that converts defun values to interpreter Nodes. Under
    ``_memoized_decode_defun``, each distinct interned value is decoded once (keyed by identity).
    """
    if _defun_decode_memo is not None:
        cached = _defun_decode_memo.get(id(value))
        if cached is not None:
            return cached
    tag, fields = _extract_defun(value, _ARITY)
    cls = SUPPORTED[tag]
    decoded = cls(*[_decode_field_defun(field) for field in fields])
    if _defun_decode_memo is not None:
        _defun_decode_memo[id(value)] = decoded
    return decoded


def defunctionalize(node: Node) -> str:
    """Compile a lambda term to defunctionalized Python source (a module of closure classes).

    Runs in a large-stack thread: the interpreter's substitution recursion can be as deep as the term,
    which overflows the C stack on Python 3.12+ (which caps C recursion regardless of
    ``setrecursionlimit``); ``run_in_large_stack`` gives it a 1 GiB stack and a high recursion limit.
    """
    def work() -> str:
        module = build(app(DEFUN, quote_binnat(node)))
        _reset_gensym()
        with memoized_decode():
            decoded = decode(module)
        assert isinstance(decoded, ast.Module)
        canonical_module = _canonicalize_classes(decoded)
        return ast.unparse(ast.fix_missing_locations(canonical_module))

    return run_in_large_stack(work)


def _defun_globals() -> dict:
    return {
        "Thunk": Thunk,
        "interned": interned,
    }


def load_namespace(source: str) -> dict:
    """Execute defunctionalized source and return the whole module namespace.

    The namespace holds every generated closure class (each carrying its ``__intern_pool__``) and the
    ``compiled`` value, so a caller can both run the program and inspect its tabled objects.
    """
    namespace = _defun_globals()
    exec(compile(source, "<defun>", "exec"), namespace)  # noqa: S102
    return namespace


def load(source: str) -> object:
    """Execute defunctionalized source and return the ``compiled`` value."""
    return load_namespace(source)["compiled"]


def defunctionalize_and_load(node: Node) -> object:
    """Compile a lambda term to defunctionalized code and load the resulting value."""
    return load(defunctionalize(node))


# A self-contained import header so a generated defunctionalized module runs on its own: it binds the
# exactly two runtime free names the generated code references (``Thunk``, ``interned``). ``interned``
# applies ``dataclass(eq=False)`` itself, so generated classes carry only ``@interned``.
_DEFUN_MODULE_HEADER = (
    "# Generated, self-contained module: the import header is added at serialization time (see\n"
    "# co_lambda._defunctionalize.runnable_defun_module); the body is emitted by the DEFUN lambda\n"
    "# term and content-addressed by compiled dataclass shape.\n"
    "from co_lambda._defun_runtime import Lambda, Thunk, interned\n"
)


def runnable_defun_module(source: str) -> str:
    """Prepend the runtime import header so a defunctionalized module is importable on its own."""
    return _DEFUN_MODULE_HEADER + "\n" + source


def defun_compiler_source() -> str:
    """The defunctionalization compiler ``DEFUN`` self-compiled to a runnable dataclass module.

    This is the dataclass-form ``compiled compiler``: ``DEFUN`` defunctionalized by itself. Importing
    the result binds ``compiled`` to the defunctionalized ``DEFUN`` value; applying it (through a
    ``Thunk``) to a quoted program yields that program's compiled Scott ``ast.Module`` as a
    defunctionalized value.
    """
    from co_lambda._defun_codegen import DEFUN

    return runnable_defun_module(defunctionalize(build(DEFUN)))


def compile_with_defun(engine: object, node: Node) -> str:
    """Compile ``node`` by RUNNING a defunctionalized ``DEFUN`` engine (the dataclass compiled compiler).

    ``engine`` is the ``compiled`` value of a ``defun_compiler_source`` module. The node is quoted and
    itself defunctionalized to feed the engine a defunctionalized Scott source value; the engine's
    output (a defunctionalized Scott ``ast.Module``) is reified, decoded, canonicalized, and unparsed,
    yielding exactly what the in-process ``defunctionalize`` produces, by self-hosting.
    """
    quoted_argument = defunctionalize_and_load(build(quote_binnat(node)))

    def work() -> str:
        result = Thunk(engine, quoted_argument).weak_head_normal_form
        if result is _BOTTOM:
            raise ValueError("the defunctionalized compiler did not produce a module")
        _reset_defun_gensym()
        with _memoized_decode_defun():
            decoded = decode_defun(result)
        assert isinstance(decoded, ast.Module)
        canonical_module = _canonicalize_classes(decoded)
        return ast.unparse(ast.fix_missing_locations(canonical_module))

    return run_in_large_stack(work)


def reify(value: object, depth: int = 0) -> Node:
    """Read a defunctionalized value back to an interpreter ``Node``.

    Forces ``Thunk.weak_head_normal_form`` to reach a closure (a defunctionalized dataclass with
    ``__call__``) or a neutral term (``Node``), then probes closures under a fresh neutral binder
    to read their body.
    """
    from co_lambda._ast import Node as AstNode, make_app, make_lam, make_var

    if _is_thunk(value):
        whnf = value.weak_head_normal_form
        if whnf is _BOTTOM:
            raise ValueError("reify: hit bottom (unproductive cycle)")
        return reify(whnf, depth)

    if isinstance(value, AstNode):
        return _reify_node(value, depth)

    if callable(value):
        probe = make_var(depth)
        result = value(probe)
        return make_lam(reify(result, depth + 1))

    raise ValueError(f"reify: cannot read back {value!r}")


def _reify_node(node: Node, depth: int) -> Node:
    """Read back an interpreter Node that appears as a neutral term in defunctionalized output.

    Probe variables are created as ``make_var(level)`` where ``level`` is the depth at probe time.
    When quoting back, a variable at level ``l`` under ``depth`` binders has de Bruijn index
    ``depth - l - 1``. Sub-terms of neutral applications may be defunctionalized values (when a
    closure was probed with a neutral variable); these are handed back to ``reify``.
    """
    from co_lambda._ast import App, Var, make_app, make_lam, make_var

    whnf = node.weak_head_normal_form
    match whnf:
        case Var(index=level):
            return make_var(depth - level - 1)
        case App(function=function, argument=argument):
            return make_app(reify(function, depth), reify(argument, depth))
        case _:
            raise ValueError(f"reify: unexpected weak head normal form in neutral term: {whnf!r}")
