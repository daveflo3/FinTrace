from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from fintrace.domain import Confidence
from fintrace.register import AssumptionRegister, Evidence, RegisterError


START = datetime(2026, 1, 1, tzinfo=timezone.utc)
LATER = datetime(2026, 2, 1, tzinfo=timezone.utc)


def source() -> Evidence:
    return Evidence(id="report", title="FY25 report", publisher="Example plc",
                    source_uri="https://example.com/report", published_on=date(2025, 1, 1))


def register_with_assumption() -> AssumptionRegister:
    r = AssumptionRegister()
    r.add_evidence(source())
    r.add_assumption(id="growth", label="Revenue growth", value=0.07, unit="decimal",
                     rationale="Historical demand plus new capacity", confidence=Confidence.MEDIUM,
                     evidence_ids=("report",), changed_by="analyst", recorded_at=START)
    return r


def test_register_traces_evidence() -> None:
    r = register_with_assumption()
    graph = r.to_graph()
    assert [n.id for n in graph.path("evidence:report", "assumption:growth")] == [
        "evidence:report", "assumption:growth"
    ]


def test_revision_preserves_older_judgement() -> None:
    r = register_with_assumption()
    r.revise("growth", value=0.05, rationale="Lower new capacity assumption",
             confidence=Confidence.LOW, evidence_ids=("report",),
             changed_by="analyst", recorded_at=LATER)
    history = r.assumptions["growth"].revisions
    assert [h.value for h in history] == [0.07, 0.05]
    assert [h.revision for h in history] == [1, 2]
    assert r.to_graph().get("assumption:growth").value == 0.05


def test_json_round_trip(tmp_path) -> None:
    r = register_with_assumption()
    path = tmp_path / "nested" / "register.json"
    r.save_json(path)
    loaded = AssumptionRegister.load_json(path)
    assert loaded.model_dump(mode="json") == r.model_dump(mode="json")
    assert loaded.evidence["report"].published_on == date(2025, 1, 1)


def test_unknown_source_is_rejected_without_mutation() -> None:
    r = register_with_assumption()
    with pytest.raises(RegisterError, match="Unknown evidence"):
        r.revise("growth", value=0.1, rationale="Test", confidence=Confidence.HIGH,
                 evidence_ids=("not-real",), changed_by="analyst", recorded_at=LATER)
    assert len(r.assumptions["growth"].revisions) == 1


def test_stale_evidence_and_missing_support_are_flagged() -> None:
    r = register_with_assumption()
    r.add_assumption(id="margin", label="Margin", value=0.2, unit="decimal",
                     rationale="Analyst judgement", confidence=Confidence.LOW,
                     changed_by="analyst", recorded_at=START)
    findings = r.review(as_of=date(2026, 10, 1), stale_after_days=365)
    assert {(f.assumption_id, f.code) for f in findings} == {
        ("growth", "POTENTIALLY_STALE_EVIDENCE"),
        ("margin", "UNSUPPORTED_ASSUMPTION"),
    }


def test_bad_revision_order_and_naive_time_rejected() -> None:
    r = register_with_assumption()
    with pytest.raises(ValidationError, match="timezone"):
        r.revise("growth", value=0.05, rationale="Changed", confidence=Confidence.MEDIUM,
                 evidence_ids=("report",), changed_by="analyst",
                 recorded_at=datetime(2026, 2, 1))
    with pytest.raises(ValidationError, match="chronological"):
        r.revise("growth", value=0.05, rationale="Changed", confidence=Confidence.MEDIUM,
                 evidence_ids=("report",), changed_by="analyst",
                 recorded_at=datetime(2025, 12, 1, tzinfo=timezone.utc))


def test_invalid_persisted_reference_is_rejected(tmp_path) -> None:
    r = register_with_assumption()
    payload = r.model_dump(mode="json")
    payload["evidence"] = {}
    with pytest.raises(ValidationError, match="Missing evidence"):
        AssumptionRegister.model_validate(payload)


def test_duplicate_evidence_is_rejected() -> None:
    r = register_with_assumption()
    with pytest.raises(RegisterError, match="already exists"):
        r.add_evidence(source())
