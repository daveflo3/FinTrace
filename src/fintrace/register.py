"""Auditable assumption and evidence register; no forecast decisions are made here."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain import Confidence, Node, NodeKind
from .graph import LineageGraph


class RegisterError(ValueError):
    """A register write violates referential integrity or revision rules."""


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"


class Evidence(BaseModel):
    """Source evidence, explicitly attributed to a dated document or observation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    source_uri: str = Field(min_length=1)
    published_on: date | None = None
    retrieved_on: date | None = None
    excerpt: str | None = None
    page: str | None = None
    notes: str | None = None


class AssumptionRevision(BaseModel):
    """Append-only history record: what the analyst believed, and when."""

    model_config = ConfigDict(frozen=True)

    revision: int = Field(ge=1)
    recorded_at: datetime
    value: float = Field(allow_inf_nan=False)
    unit: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    confidence: Confidence
    evidence_ids: tuple[str, ...] = ()
    changed_by: str = Field(min_length=1)

    @model_validator(mode="after")
    def unique_evidence(self) -> "AssumptionRevision":
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("Duplicate evidence references are not allowed.")
        return self


class Assumption(BaseModel):
    """Stable identity, with revision history preserving earlier analyst reasoning."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    revisions: tuple[AssumptionRevision, ...] = Field(min_length=1)

    @property
    def current(self) -> AssumptionRevision:
        return self.revisions[-1]

    @model_validator(mode="after")
    def valid_sequence(self) -> "Assumption":
        numbers = [r.revision for r in self.revisions]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError("Assumption revisions must be contiguous, starting at 1.")
        times = [r.recorded_at for r in self.revisions]
        if any(t.tzinfo is None or t.utcoffset() is None for t in times):
            raise ValueError("Revision timestamps must include a timezone.")
        if times != sorted(times):
            raise ValueError("Revision timestamps must be chronological.")
        return self


class ReviewFinding(BaseModel):
    code: str
    severity: FindingSeverity
    assumption_id: str
    message: str
    evidence_id: str | None = None


class AssumptionRegister(BaseModel):
    """Validated evidence store plus append-only assumption versions.

    This is a data provenance layer, not an investment signal or an automated
    evidence credibility ranking. Freshness thresholds are analyst-configurable.
    """

    evidence: dict[str, Evidence] = Field(default_factory=dict)
    assumptions: dict[str, Assumption] = Field(default_factory=dict)

    @model_validator(mode="after")
    def valid_references(self) -> "AssumptionRegister":
        for key, source in self.evidence.items():
            if key != source.id:
                raise ValueError(f"Evidence key mismatch: {key}")
        for key, assumption in self.assumptions.items():
            if key != assumption.id:
                raise ValueError(f"Assumption key mismatch: {key}")
            for revision in assumption.revisions:
                unknown = set(revision.evidence_ids).difference(self.evidence)
                if unknown:
                    raise ValueError(f"Missing evidence for {key}: {sorted(unknown)}")
        return self

    def add_evidence(self, source: Evidence) -> None:
        if source.id in self.evidence:
            raise RegisterError(f"Evidence '{source.id}' already exists.")
        self.evidence[source.id] = source

    def add_assumption(
        self,
        *,
        id: str,
        label: str,
        value: float,
        unit: str,
        rationale: str,
        confidence: Confidence,
        evidence_ids: tuple[str, ...] = (),
        changed_by: str,
        recorded_at: datetime | None = None,
    ) -> Assumption:
        if id in self.assumptions:
            raise RegisterError(f"Assumption '{id}' already exists.")
        self._check_evidence(evidence_ids)
        revision = AssumptionRevision(
            revision=1,
            recorded_at=recorded_at or datetime.now(timezone.utc),
            value=value,
            unit=unit,
            rationale=rationale,
            confidence=confidence,
            evidence_ids=evidence_ids,
            changed_by=changed_by,
        )
        assumption = Assumption(id=id, label=label, revisions=(revision,))
        self.assumptions[id] = assumption
        return assumption

    def revise(
        self,
        id: str,
        *,
        value: float,
        rationale: str,
        confidence: Confidence,
        evidence_ids: tuple[str, ...],
        changed_by: str,
        recorded_at: datetime | None = None,
    ) -> Assumption:
        if id not in self.assumptions:
            raise RegisterError(f"Unknown assumption '{id}'.")
        self._check_evidence(evidence_ids)
        previous = self.assumptions[id]
        next_revision = AssumptionRevision(
            revision=len(previous.revisions) + 1,
            recorded_at=recorded_at or datetime.now(timezone.utc),
            value=value,
            unit=previous.current.unit,
            rationale=rationale,
            confidence=confidence,
            evidence_ids=evidence_ids,
            changed_by=changed_by,
        )
        # Validate replacement before mutating. Historical revisions are retained.
        revised = Assumption(
            id=previous.id,
            label=previous.label,
            revisions=(*previous.revisions, next_revision),
        )
        self.assumptions[id] = revised
        return revised

    def _check_evidence(self, ids: tuple[str, ...]) -> None:
        missing = set(ids).difference(self.evidence)
        if missing:
            raise RegisterError(f"Unknown evidence ID(s): {', '.join(sorted(missing))}")

    def review(
        self, *, as_of: date | None = None, stale_after_days: int = 365
    ) -> list[ReviewFinding]:
        """Raise review questions, not automatic recommendations or truth claims."""
        if stale_after_days < 0:
            raise ValueError("stale_after_days must be nonnegative")
        today = as_of or date.today()
        findings: list[ReviewFinding] = []
        for assumption in self.assumptions.values():
            current = assumption.current
            if not current.evidence_ids:
                findings.append(ReviewFinding(
                    code="UNSUPPORTED_ASSUMPTION", severity=FindingSeverity.WARNING,
                    assumption_id=assumption.id,
                    message="No source evidence is linked; ask the analyst to document support.",
                ))
            for evidence_id in current.evidence_ids:
                source = self.evidence[evidence_id]
                if source.published_on is None:
                    findings.append(ReviewFinding(
                        code="UNDATED_EVIDENCE", severity=FindingSeverity.INFO,
                        assumption_id=assumption.id, evidence_id=evidence_id,
                        message="The evidence has no publication date; review its relevance.",
                    ))
                elif (today - source.published_on).days > stale_after_days:
                    findings.append(ReviewFinding(
                        code="POTENTIALLY_STALE_EVIDENCE", severity=FindingSeverity.INFO,
                        assumption_id=assumption.id, evidence_id=evidence_id,
                        message=f"Evidence is {(today - source.published_on).days} days old; check for updates.",
                    ))
        return findings

    def to_graph(self) -> LineageGraph:
        """Make all current evidence -> assumption relationships explorable."""
        graph = LineageGraph()
        for source in self.evidence.values():
            graph.add_node(Node(
                id=f"evidence:{source.id}", kind=NodeKind.EVIDENCE,
                label=source.title, source_uri=source.source_uri,
                source_quote=source.excerpt,
                metadata={"publisher": source.publisher, "page": source.page},
            ))
        for assumption in self.assumptions.values():
            current = assumption.current
            graph.add_node(Node(
                id=f"assumption:{assumption.id}", kind=NodeKind.ASSUMPTION,
                label=assumption.label, value=current.value, unit=current.unit,
                rationale=current.rationale, confidence=current.confidence,
                metadata={"revision": current.revision, "owner": current.changed_by},
            ))
            for evidence_id in current.evidence_ids:
                graph.link(f"evidence:{evidence_id}", f"assumption:{assumption.id}", "supports")
        return graph

    def save_json(self, path: str | Path) -> None:
        """Write JSON atomically to reduce the risk of truncated local files."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True)
        temporary: str | None = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=destination.parent,
                                    prefix=f".{destination.name}.", suffix=".tmp", delete=False) as temp:
                temporary = temp.name
                temp.write(payload + "\n")
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def load_json(cls, path: str | Path) -> "AssumptionRegister":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))
