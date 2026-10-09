"""Create two tiny financial models and demonstrate FinTrace version intelligence."""
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook
from openpyxl.workbook.defined_name import DefinedName

from fintrace.compare import ModelComparator


def build(path: Path, growth: float) -> None:
    wb = Workbook()
    inputs = wb.active
    inputs.title = "Inputs"
    model = wb.create_sheet("Model")

    inputs["A1"] = "Revenue"
    inputs["B1"] = 1000
    inputs["A2"] = "Revenue Growth"
    inputs["B2"] = growth
    inputs["B2"].number_format = "0.0%"
    wb.defined_names.add(DefinedName("RevenueGrowth", attr_text="'Inputs'!$B$2"))

    model["A1"] = "Forecast Revenue"
    model["B1"] = "='Inputs'!B1*(1+RevenueGrowth)"
    model["A2"] = "Free Cash Flow"
    model["B2"] = "=B1*0.20"
    wb.save(path)


with TemporaryDirectory() as directory:
    root = Path(directory)
    old = root / "model_v1.xlsx"
    new = root / "model_v2.xlsx"
    build(old, 0.08)
    build(new, 0.06)

    report = ModelComparator().compare_files(old, new)
    for change in report.changes:
        before = change.before_value if change.before_value is not None else change.before_formula
        after = change.after_value if change.after_value is not None else change.after_formula
        print(f"{change.ref}: {before} -> {after} [{change.classification.value}]")
        if change.impacted_outputs:
            print("  impacts:", ", ".join(change.impacted_outputs))
