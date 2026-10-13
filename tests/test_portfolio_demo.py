"""Regression checks for the committed, fully synthetic portfolio examples."""

from pathlib import Path

from fintrace.compare import ChangeClassification, ModelComparator
from fintrace.excel import ExcelIngestor


FIXTURES = Path(__file__).parent.parent / "examples" / "sample_models"


def test_portfolio_workbooks_have_a_real_dependency_chain() -> None:
    snapshot = ExcelIngestor().inspect(FIXTURES / "model_v2.xlsx")
    edges = {(d.upstream, d.downstream) for d in snapshot.dependencies}
    assert ("'Historical Actuals'!B4", "'Forecast'!B4") in edges
    assert ("'Assumptions'!B4", "'Forecast'!B4") in edges
    assert ("'Forecast'!B4", "'Forecast'!B5") in edges
    assert ("'Forecast'!B5", "'Forecast'!B6") in edges
    assert ("'Forecast'!B6", "'Forecast'!B7") in edges
    assert not snapshot.warnings


def test_historical_change_is_not_misclassified_as_an_assumption() -> None:
    report = ModelComparator().compare_files(
        FIXTURES / "model_v1.xlsx", FIXTURES / "model_v2.xlsx"
    )
    changes = {c.ref: c for c in report.changes}
    assert len(changes) == 3
    assert changes["'Historical Actuals'!B4"].classification is ChangeClassification.REPORTED_ACTUAL
    assert changes["'Assumptions'!B4"].classification is ChangeClassification.ASSUMPTION
    assert changes["'Assumptions'!B5"].classification is ChangeClassification.ASSUMPTION
    assert "'Forecast'!B7" in changes["'Historical Actuals'!B4"].impacted_outputs
    assert "'Forecast'!B7" in changes["'Assumptions'!B4"].impacted_outputs
    assert not report.warnings
