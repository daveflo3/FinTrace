from __future__ import annotations

from collections.abc import Iterable

import networkx as nx

from .domain import Node


class FinTraceGraphError(ValueError):
    """Raised when the lineage graph violates a FinTrace integrity rule."""


class LineageGraph:
    """Directed acyclic graph of financial reasoning."""

    def __init__(self) -> None:
        self._graph = nx.DiGraph()
        self._nodes: dict[str, Node] = {}

    def add_node(self, node: Node) -> None:
        if node.id in self._nodes:
            raise FinTraceGraphError(f"Duplicate node id: {node.id}")
        self._nodes[node.id] = node
        self._graph.add_node(node.id)

    def add_nodes(self, nodes: Iterable[Node]) -> None:
        for node in nodes:
            self.add_node(node)

    def link(self, upstream_id: str, downstream_id: str, relation: str = "feeds") -> None:
        if upstream_id == downstream_id:
            raise FinTraceGraphError("A node cannot depend on itself.")

        missing = [node_id for node_id in (upstream_id, downstream_id) if node_id not in self._nodes]
        if missing:
            raise FinTraceGraphError(f"Unknown node id(s): {', '.join(missing)}")

        self._graph.add_edge(upstream_id, downstream_id, relation=relation)

        if not nx.is_directed_acyclic_graph(self._graph):
            self._graph.remove_edge(upstream_id, downstream_id)
            raise FinTraceGraphError(
                f"Link {upstream_id} -> {downstream_id} would create a cycle."
            )

    def get(self, node_id: str) -> Node:
        try:
            return self._nodes[node_id]
        except KeyError as exc:
            raise FinTraceGraphError(f"Unknown node id: {node_id}") from exc

    def upstream(self, node_id: str) -> list[Node]:
        self.get(node_id)
        ids = nx.ancestors(self._graph, node_id)
        return [self._nodes[i] for i in nx.topological_sort(self._graph) if i in ids]

    def downstream(self, node_id: str) -> list[Node]:
        self.get(node_id)
        ids = nx.descendants(self._graph, node_id)
        return [self._nodes[i] for i in nx.topological_sort(self._graph) if i in ids]

    def path(self, upstream_id: str, downstream_id: str) -> list[Node]:
        self.get(upstream_id)
        self.get(downstream_id)
        try:
            ids = nx.shortest_path(self._graph, upstream_id, downstream_id)
        except nx.NetworkXNoPath as exc:
            raise FinTraceGraphError(
                f"No lineage path from {upstream_id} to {downstream_id}."
            ) from exc
        return [self._nodes[i] for i in ids]

    def relation(self, upstream_id: str, downstream_id: str) -> str | None:
        edge = self._graph.get_edge_data(upstream_id, downstream_id)
        return None if edge is None else edge.get("relation")

    def roots_for(self, node_id: str) -> list[Node]:
        """Return source nodes upstream of a target that have no predecessors."""
        upstream_ids = {node.id for node in self.upstream(node_id)}
        roots = [
            node_id_
            for node_id_ in upstream_ids
            if self._graph.in_degree(node_id_) == 0
        ]
        return [self._nodes[i] for i in roots]

    def nodes(self) -> list[Node]:
        return list(self._nodes.values())

    def edges(self) -> list[tuple[str, str, str]]:
        return [
            (a, b, data.get("relation", "feeds"))
            for a, b, data in self._graph.edges(data=True)
        ]
