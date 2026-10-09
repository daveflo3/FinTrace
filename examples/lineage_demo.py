from fintrace.domain import Confidence, Node, NodeKind
from fintrace.graph import LineageGraph


def main() -> None:
    graph = LineageGraph()

    evidence = Node(
        id="evidence.management-guidance",
        kind=NodeKind.EVIDENCE,
        label="Management guidance",
        description="Management expects mid-single-digit volume growth.",
        source_uri="annual-report://example/fy2025",
    )
    assumption = Node(
        id="assumption.revenue-growth",
        kind=NodeKind.ASSUMPTION,
        label="FY27 revenue growth",
        value=0.065,
        rationale="Selected near the top of guidance due to new capacity.",
        confidence=Confidence.MEDIUM,
    )
    output = Node(
        id="output.equity-value",
        kind=NodeKind.OUTPUT,
        label="Implied equity value",
        value=24.7,
        unit="GBP bn",
    )

    graph.add_nodes([evidence, assumption, output])
    graph.link(evidence.id, assumption.id, "supports")
    graph.link(assumption.id, output.id, "influences")

    print("Trace:")
    for node in graph.path(evidence.id, output.id):
        print(f"- {node.kind.value}: {node.label}")


if __name__ == "__main__":
    main()
