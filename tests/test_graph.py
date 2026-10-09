import pytest

from fintrace.domain import Node, NodeKind
from fintrace.graph import FinTraceGraphError, LineageGraph


def node(node_id: str, kind: NodeKind = NodeKind.CALCULATION) -> Node:
    return Node(id=node_id, kind=kind, label=node_id)


def test_trace_from_evidence_to_output() -> None:
    graph = LineageGraph()
    graph.add_nodes(
        [
            node("evidence", NodeKind.EVIDENCE),
            node("assumption", NodeKind.ASSUMPTION),
            node("output", NodeKind.OUTPUT),
        ]
    )
    graph.link("evidence", "assumption", "supports")
    graph.link("assumption", "output", "feeds")

    assert [n.id for n in graph.path("evidence", "output")] == [
        "evidence",
        "assumption",
        "output",
    ]


def test_cycle_is_rejected() -> None:
    graph = LineageGraph()
    graph.add_nodes([node("a"), node("b")])
    graph.link("a", "b")

    with pytest.raises(FinTraceGraphError, match="cycle"):
        graph.link("b", "a")


def test_unknown_node_is_rejected() -> None:
    graph = LineageGraph()
    graph.add_node(node("a"))

    with pytest.raises(FinTraceGraphError, match="Unknown node"):
        graph.link("a", "missing")


def test_roots_for_returns_source_nodes() -> None:
    graph = LineageGraph()
    graph.add_nodes(
        [
            node("source-1", NodeKind.EVIDENCE),
            node("source-2", NodeKind.EVIDENCE),
            node("assumption", NodeKind.ASSUMPTION),
            node("output", NodeKind.OUTPUT),
        ]
    )
    graph.link("source-1", "assumption")
    graph.link("source-2", "assumption")
    graph.link("assumption", "output")

    assert {n.id for n in graph.roots_for("output")} == {"source-1", "source-2"}
