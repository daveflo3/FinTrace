"""Synthetic example; nothing here is a real-company forecast."""
from datetime import date, datetime, timezone
from pathlib import Path

from fintrace.domain import Confidence
from fintrace.register import AssumptionRegister, Evidence


def main() -> None:
    register = AssumptionRegister()
    register.add_evidence(Evidence(
        id="hypothetical-guidance",
        title="Illustrative FY25 guidance", publisher="Example plc (fictional)",
        source_uri="example://illustrative-management-guidance",
        published_on=date(2025, 6, 1),
        excerpt="Illustrative assumption: mid-single-digit revenue growth.",
    ))
    register.add_assumption(
        id="fy27-revenue-growth", label="FY27 revenue growth",
        value=0.065, unit="decimal", changed_by="example-analyst",
        rationale="Illustratively near the top of guidance due to capacity expansion.",
        confidence=Confidence.MEDIUM, evidence_ids=("hypothetical-guidance",),
        recorded_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    destination = Path("outputs/assumption_register_demo.json")
    register.save_json(destination)
    print(f"Saved {destination}")
    for finding in register.review(as_of=date(2026, 10, 9)):
        print(f"{finding.severity}: {finding.code}: {finding.message}")
    graph = register.to_graph()
    print("Trace:", [node.id for node in graph.path(
        "evidence:hypothetical-guidance", "assumption:fy27-revenue-growth"
    )])


if __name__ == "__main__":
    main()
