from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .compare import ModelComparator
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


@app.command("compare-excel")
def compare_excel(
    old_workbook: Path = typer.Argument(..., exists=True, readable=True, help="Older .xlsx/.xlsm model."),
    new_workbook: Path = typer.Argument(..., exists=True, readable=True, help="Newer .xlsx/.xlsm model."),
    json_out: Path | None = typer.Option(None, "--json-out", help="Optional JSON change-report output path."),
) -> None:
    """Compare two workbook versions and trace changed cells to downstream outputs."""
    report = ModelComparator().compare_files(old_workbook, new_workbook)

    console.print(f"[bold]{report.old_workbook}[/bold] → [bold]{report.new_workbook}[/bold]")
    console.print(
        f"{len(report.changes)} change(s) · {len(report.assumption_changes)} assumption candidate change(s) · "
        f"{len(report.formula_changes)} formula change(s)"
    )

    table = Table(title="Model changes")
    table.add_column("Cell")
    table.add_column("Classification")
    table.add_column("Before")
    table.add_column("After")
    table.add_column("Impacted outputs")
    for change in report.changes[:30]:
        before = change.before_value if change.before_value is not None else change.before_formula
        after = change.after_value if change.after_value is not None else change.after_formula
        table.add_row(
            change.ref,
            change.classification.value,
            "" if before is None else str(before),
            "" if after is None else str(after),
            ", ".join(change.impacted_outputs),
        )
    console.print(table)

    if report.warnings:
        console.print(f"[yellow]{len(report.warnings)} parser warning(s) carried into comparison.[/yellow]")
    if json_out is not None:
        report.save_json(json_out)
        console.print(f"Change report written to {json_out}")


if __name__ == "__main__":
    app()
