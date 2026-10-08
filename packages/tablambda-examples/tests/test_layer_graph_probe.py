"""Probe for the paper's per-node evaluator and graph-as-layer-assignment account.

The paper's ``Tabled``/``WHNF`` pseudocode solves ONE layer per demanded term; the GRAPH of a
term is the induced layer assignment: the interned terms hereditarily reachable from it
through exposed layers, each carrying the layer the solver computes on demand. Enumerating
that graph is metalanguage observation (exactly what this test does), not an operation of the
calculus. Before the LaTeX states this account, the probe machine-checks it on the three
regimes of the paper's case study:

- ``ed`` on ``"ab"``/``"cd"`` (terminating, acyclic): the enumeration terminates on a finite
  node set;
- ``Y (cons 0)`` (productive cycle): the enumeration terminates although the unfolded tree is
  infinite, and the tail ``W.W`` is an already-interned node whose layer is pointer-identical
  to the root's layer, the back edge;
- ``Omega`` (unproductive cycle): the layer is ``BOTTOM`` and the graph is the single node.

Every enumerated layer must be a value: ``BOTTOM`` or its own weak head normal form.
"""

from __future__ import annotations

import sys

from collections import deque
from dataclasses import dataclass
from typing import final

from syrupy.assertion import SnapshotAssertion

from tablambda._ast import BOTTOM, App, Lam, Node, Var, WeakHeadBottom
from tablambda._dsl import app, build
from tablambda._prelude import SELF_APPLY
from tablambda._shape import weak_head_normalize
from tablambda_examples._cyclic_zeros import STREAM, W_APPLIED
from tablambda_examples._editdistance import EDIT_DISTANCE, _string_to_list

_NODE_CAP = 200_000
_RECURSION_LIMIT = 100_000


@final
@dataclass(kw_only=True, slots=True, frozen=True, weakref_slot=True)
class GraphEntry:
    """One node of the enumerated graph: the interned term and its solved layer."""

    node: Node
    layer: "Node | WeakHeadBottom"


def _layer_sub_terms(layer: "Node | WeakHeadBottom") -> "tuple[Node, ...]":
    match layer:
        case WeakHeadBottom.BOTTOM | Var():
            return ()
        case Lam(body=body):
            return (body,)
        case App(function=function, argument=argument):
            return (function, argument)
        case _:
            raise TypeError(f"unexpected layer {layer!r}")


def enumerate_layer_graph(root: Node) -> "dict[int, GraphEntry]":
    """The metalanguage enumeration of the graph of ``root``: demand one layer per hereditarily
    reachable interned term, with cycle detection on node identity (the visited set), which the
    calculus itself cannot perform."""
    graph: "dict[int, GraphEntry]" = {}
    worklist = deque([root])
    while worklist:
        node = worklist.popleft()
        if id(node) in graph:
            continue
        if len(graph) >= _NODE_CAP:
            raise ValueError(f"layer-graph enumeration exceeded {_NODE_CAP} nodes")
        layer = weak_head_normalize(node)
        graph[id(node)] = GraphEntry(node=node, layer=layer)
        worklist.extend(_layer_sub_terms(layer))
    return graph


def _assert_layers_are_values(graph: "dict[int, GraphEntry]") -> None:
    for entry in graph.values():
        if entry.layer is not BOTTOM:
            assert weak_head_normalize(entry.layer) is entry.layer, (
                f"layer of {entry.node!r} is not its own weak head normal form"
            )


def _graph_summary(graph: "dict[int, GraphEntry]") -> str:
    bottom_count = sum(1 for entry in graph.values() if entry.layer is BOTTOM)
    return f"nodes={len(graph)} bottom_layers={bottom_count}"


def test_edit_distance_layer_graph_is_finite(snapshot: SnapshotAssertion) -> None:
    alphabet = {character: index for index, character in enumerate(sorted(set("abcd")))}
    root = build(
        app(
            app(EDIT_DISTANCE, _string_to_list("ab", alphabet)),
            _string_to_list("cd", alphabet),
        )
    )
    previous_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(previous_limit, _RECURSION_LIMIT))
    try:
        graph = enumerate_layer_graph(root)
    finally:
        sys.setrecursionlimit(previous_limit)
    _assert_layers_are_values(graph)
    assert _graph_summary(graph) == snapshot(name="edit_distance_graph_summary")


def test_cyclic_zeros_layer_graph_folds_the_back_edge(snapshot: SnapshotAssertion) -> None:
    graph = enumerate_layer_graph(STREAM)
    _assert_layers_are_values(graph)
    assert id(W_APPLIED) in graph, "the tail W.W must be a node of the enumerated graph"
    assert graph[id(W_APPLIED)].layer is graph[id(STREAM)].layer, (
        "the tail's layer must be the root's layer, the folded back edge"
    )
    assert _graph_summary(graph) == snapshot(name="cyclic_zeros_graph_summary")


def test_omega_layer_graph_is_the_bottom_node() -> None:
    omega = build(app(SELF_APPLY, SELF_APPLY))
    graph = enumerate_layer_graph(omega)
    assert graph[id(omega)].layer is BOTTOM
    assert len(graph) == 1
