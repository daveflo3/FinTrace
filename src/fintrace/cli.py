from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .domain import Confidence, Node, NodeKind
from .excel import ExcelIngestor
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


@app.command("inspect-excel")
def inspect_excel(
    workbook: Path = typer.Argument(..., exists=True, readable=True, help="Path to an .xlsx/.xlsm model."),
    json_out: Path | None = typer.Option(None, "--json-out", help="Optional JSON snapshot output path."),
) -> None:
    """Map workbook structure, formula dependencies and review candidates."""
    snapshot = ExcelIngestor().inspect(workbook)

    console.print(f"[bold]{snapshot.workbook_name}[/bold]")
    console.print(
        f"{len(snapshot.sheets)} sheet(s) · {len(snapshot.cells)} non-empty cell(s) · "
        f"{len(snapshot.dependencies)} dependency edge(s)"
    )

    table = Table(title="Review candidates")
    table.add_column("Role")
    table.add_column("Cell")
    table.add_column("Score", justify="right")
    table.add_column("Why")
    for candidate in snapshot.candidates[:20]:
        table.add_row(
            candidate.role, candidate.ref, f"{candidate.score:.2f}", "; ".join(candidate.reasons)
        )
    console.print(table)

    if snapshot.warnings:
        console.print(f"[yellow]{len(snapshot.warnings)} parser warning(s).[/yellow]")
    if json_out is not None:
        snapshot.save_json(json_out)
        console.print(f"Snapshot written to {json_out}")


if __name__ == "__main__":
    app()
