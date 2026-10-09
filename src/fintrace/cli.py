from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from .domain import Confidence, Node, NodeKind
from .graph import LineageGraph

app = typer.Typer(help="FinTrace — traceable financial judgement.")
console = Console()


@app.callback()
def main() -> None:
    """FinTrace command-line entrypoint."""



def _demo_graph() -> LineageGraph:
    graph = LineageGraph()
    graph.add_nodes(
        [
            Node(
                id="guidance",
                kind=NodeKind.EVIDENCE,
                label="Management revenue guidance",
                description="Management expects mid-single-digit growth.",
                source_uri="annual-report://example",
            ),
            Node(
                id="growth",
                kind=NodeKind.ASSUMPTION,
                label="FY27 revenue growth",
                value=0.065,
                unit="decimal",
                rationale="Midpoint of guidance adjusted for recent momentum.",
                confidence=Confidence.MEDIUM,
            ),
            Node(
                id="revenue",
                kind=NodeKind.CALCULATION,
                label="FY27 revenue forecast",
                value=1065,
                unit="GBP m",
            ),
            Node(
                id="fcf",
                kind=NodeKind.OUTPUT,
                label="FY27 free cash flow",
                value=220,
                unit="GBP m",
            ),
            Node(
                id="valuation",
                kind=NodeKind.OUTPUT,
                label="DCF equity value",
                value=2470,
                unit="GBP m",
            ),
        ]
    )

    graph.link("guidance", "growth", "supports")
    graph.link("growth", "revenue", "drives")
    graph.link("revenue", "fcf", "feeds")
    graph.link("fcf", "valuation", "feeds")
    return graph


@app.command()
def demo() -> None:
    """Run a tiny end-to-end lineage example."""
    graph = _demo_graph()
    trace = graph.path("guidance", "valuation")

    table = Table(title="FinTrace lineage demo")
    table.add_column("Type")
    table.add_column("Node")
    table.add_column("Value")

    for node in trace:
        value = "" if node.value is None else str(node.value)
        if node.unit:
            value = f"{value} {node.unit}"
        table.add_row(node.kind.value, node.label, value)

    console.print(table)


if __name__ == "__main__":
    app()
