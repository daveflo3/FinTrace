"""Portfolio walkthrough using two fully fictional Excel financial models.

Run from the repository root after `pip install -e ".[dev,excel]"`:
    python examples/portfolio_demo.py

The application maps changed financial inputs and their *possible* downstream
impact, but deliberately does not recalculate Excel or attribute valuation moves.
"""

from __future__ import annotations

from pathlib import Path

from fintrace.compare import ChangeClassification, ModelComparator
from fintrace.excel import ExcelIngestor

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).resolve().parent / "sample_models"


def describe_value(classification: ChangeClassification, value: object) -> str:
    """Human presentation is demo-only; the comparator stores raw values."""
    if isinstance(value, (int, float)):
        if classification is ChangeClassification.ASSUMPTION:
            return f"{value:.1%}"
        if classification is ChangeClassification.REPORTED_ACTUAL:
            return f"£{value:,.0f}m"
    return str(value)


def main() -> None:
    old_path = DATA / "model_v1.xlsx"
    new_path = DATA / "model_v2.xlsx"
    ingestor = ExcelIngestor()
    old = ingestor.inspect(old_path)
    new = ingestor.inspect(new_path)
    report = ModelComparator().compare(old, new)

    print("FINTRACE | PORTFOLIO DEMO")
    print("ExampleCo · fictional data · financial models in Excel")
    print("=" * 64)
    print(f"Comparing: {old.workbook_name}  →  {new.workbook_name}")
    print(f"Detected {len(report.changes)} changed model cells")
    print()

    for change in report.changes:
        before = describe_value(change.classification, change.before_value)
        after = describe_value(change.classification, change.after_value)
        label = change.label or change.ref
        role = (
            "REPORTED ACTUAL"
            if change.classification is ChangeClassification.REPORTED_ACTUAL
            else "ASSUMPTION CANDIDATE"
            if change.classification is ChangeClassification.ASSUMPTION
            else change.classification.value.upper().replace("_", " ")
        )
        print(f"[{role}] {label}")
        print(f"  Cell:     {change.ref}")
        print(f"  Revision: {before} → {after}")
        if change.impacted_outputs:
            labels = [
                new.cells[ref].label or ref
                if ref in new.cells else ref
                for ref in change.impacted_outputs
            ]
            print(f"  Trace:    {' → '.join(labels)}")
        print()

    target = ROOT / "outputs" / "portfolio_model_changes.json"
    report.save_json(target)
    print(f"Unresolved reference warnings: {len(report.warnings)}")
    print(f"Machine-readable report: {target.relative_to(ROOT)}")
    print("Note: Traced links indicate possible effects, not numeric attribution.")
    print("FinTrace neither calculates valuation changes nor recommends trades.")


if __name__ == "__main__":
    main()
