"""Model-version intelligence for FinTrace.

The comparator explains *what changed* between two workbook snapshots and traces changed
cells to downstream review-candidate outputs. Classifications are deliberately transparent
heuristics: FinTrace surfaces review questions; it does not claim to know analyst intent.
"""
from __future__ import annotations

from collections import defaultdict, deque
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .excel import CandidateRole, ExcelIngestor, WorkbookSnapshot


class ChangeKind(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    VALUE_CHANGED = "value_changed"
    FORMULA_CHANGED = "formula_changed"
    METADATA_CHANGED = "metadata_changed"


class ChangeClassification(StrEnum):
    ASSUMPTION = "candidate_assumption_change"
    REPORTED_ACTUAL = "candidate_reported_actual_change"
    INPUT_DATA = "input_data_change"
    CALCULATION = "calculation_change"
    STRUCTURAL = "structural_change"
    METADATA = "metadata_change"


class CellChange(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: str
    kind: ChangeKind
    classification: ChangeClassification
    label: str | None = None
    before_value: Any | None = None
    after_value: Any | None = None
    before_formula: str | None = None
    after_formula: str | None = None
    impacted_outputs: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


class ModelChangeReport(BaseModel):
    """Deterministic, review-oriented comparison of two workbook snapshots."""

    old_workbook: str
    new_workbook: str
    changes: tuple[CellChange, ...]
    warnings: tuple[str, ...] = ()

    @property
    def assumption_changes(self) -> tuple[CellChange, ...]:
        return tuple(
            change
            for change in self.changes
            if change.classification is ChangeClassification.ASSUMPTION
        )

    @property
    def formula_changes(self) -> tuple[CellChange, ...]:
        return tuple(
            change for change in self.changes if change.kind is ChangeKind.FORMULA_CHANGED
        )

    @property
    def structural_changes(self) -> tuple[CellChange, ...]:
        return tuple(
            change
            for change in self.changes
            if change.classification is ChangeClassification.STRUCTURAL
        )

    @property
    def impacted_output_refs(self) -> tuple[str, ...]:
        refs = {
            output
            for change in self.changes
            for output in change.impacted_outputs
        }
        return tuple(sorted(refs))

    def save_json(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")


class ModelComparator:
    """Compare workbook versions without pretending to infer financial truth."""

    ACTUAL_KEYWORDS = {
        "actual",
        "reported",
        "historical",
        "history",
        "ltm",
        "last twelve months",
    }

    def __init__(self, *, ingestor: ExcelIngestor | None = None) -> None:
        self.ingestor = ingestor or ExcelIngestor()

    def compare_files(self, old: str | Path, new: str | Path) -> ModelChangeReport:
        return self.compare(self.ingestor.inspect(old), self.ingestor.inspect(new))

    def compare(self, old: WorkbookSnapshot, new: WorkbookSnapshot) -> ModelChangeReport:
        old_candidates = self._candidate_map(old.candidates)
        new_candidates = self._candidate_map(new.candidates)
        downstream = self._downstream_graph(new)
        output_refs = {
            candidate.ref for candidate in new.candidates if candidate.role == "output"
        }

        changes: list[CellChange] = []
        all_refs = sorted(set(old.cells) | set(new.cells))
        for ref in all_refs:
            before = old.cells.get(ref)
            after = new.cells.get(ref)

            if before is None and after is not None:
                changes.append(
                    CellChange(
                        ref=ref,
                        kind=ChangeKind.ADDED,
                        classification=ChangeClassification.STRUCTURAL,
                        label=after.label,
                        after_value=after.value,
                        after_formula=after.formula,
                        impacted_outputs=self._impacted_outputs(ref, downstream, output_refs),
                        reasons=("cell exists only in the newer workbook",),
                    )
                )
                continue

            if before is not None and after is None:
                changes.append(
                    CellChange(
                        ref=ref,
                        kind=ChangeKind.REMOVED,
                        classification=ChangeClassification.STRUCTURAL,
                        label=before.label,
                        before_value=before.value,
                        before_formula=before.formula,
                        reasons=("cell exists only in the older workbook",),
                    )
                )
                continue

            assert before is not None and after is not None
            impacted = self._impacted_outputs(ref, downstream, output_refs)

            if before.formula != after.formula:
                changes.append(
                    CellChange(
                        ref=ref,
                        kind=ChangeKind.FORMULA_CHANGED,
                        classification=ChangeClassification.CALCULATION,
                        label=after.label or before.label,
                        before_formula=before.formula,
                        after_formula=after.formula,
                        impacted_outputs=impacted,
                        reasons=("formula text changed between workbook versions",),
                    )
                )
                continue

            if before.value != after.value:
                classification, reasons = self._classify_value_change(
                    ref=ref,
                    label=after.label or before.label,
                    sheet=after.sheet,
                    old_candidates=old_candidates,
                    new_candidates=new_candidates,
                )
                changes.append(
                    CellChange(
                        ref=ref,
                        kind=ChangeKind.VALUE_CHANGED,
                        classification=classification,
                        label=after.label or before.label,
                        before_value=before.value,
                        after_value=after.value,
                        impacted_outputs=impacted,
                        reasons=reasons,
                    )
                )
                continue

            if (
                before.label != after.label
                or before.number_format != after.number_format
                or before.named_ranges != after.named_ranges
            ):
                changes.append(
                    CellChange(
                        ref=ref,
                        kind=ChangeKind.METADATA_CHANGED,
                        classification=ChangeClassification.METADATA,
                        label=after.label or before.label,
                        impacted_outputs=impacted,
                        reasons=("label, number format or defined-name metadata changed",),
                    )
                )

        warnings = tuple(dict.fromkeys((*old.warnings, *new.warnings)))
        return ModelChangeReport(
            old_workbook=old.workbook_name,
            new_workbook=new.workbook_name,
            changes=tuple(changes),
            warnings=warnings,
        )

    @staticmethod
    def _candidate_map(candidates: tuple[CandidateRole, ...]) -> dict[str, set[str]]:
        roles: dict[str, set[str]] = defaultdict(set)
        for candidate in candidates:
            roles[candidate.ref].add(candidate.role)
        return roles

    def _classify_value_change(
        self,
        *,
        ref: str,
        label: str | None,
        sheet: str,
        old_candidates: dict[str, set[str]],
        new_candidates: dict[str, set[str]],
    ) -> tuple[ChangeClassification, tuple[str, ...]]:
        if "assumption" in old_candidates.get(ref, set()) | new_candidates.get(ref, set()):
            return (
                ChangeClassification.ASSUMPTION,
                ("cell is an assumption review candidate in at least one workbook version",),
            )

        context = f"{label or ''} {sheet}".lower()
        if any(keyword in context for keyword in self.ACTUAL_KEYWORDS):
            return (
                ChangeClassification.REPORTED_ACTUAL,
                ("label/sheet contains historical or reported-actual language",),
            )

        return (
            ChangeClassification.INPUT_DATA,
            ("literal input changed but was not classified as an assumption candidate",),
        )

    @staticmethod
    def _downstream_graph(snapshot: WorkbookSnapshot) -> dict[str, set[str]]:
        graph: dict[str, set[str]] = defaultdict(set)
        for edge in snapshot.dependencies:
            graph[edge.upstream].add(edge.downstream)
        return graph

    @staticmethod
    def _impacted_outputs(
        start: str,
        downstream: dict[str, set[str]],
        output_refs: set[str],
    ) -> tuple[str, ...]:
        seen = {start}
        queue: deque[str] = deque([start])
        impacted: set[str] = set()

        while queue:
            node = queue.popleft()
            for child in downstream.get(node, set()):
                if child in seen:
                    continue
                seen.add(child)
                queue.append(child)
                if child in output_refs:
                    impacted.add(child)

        return tuple(sorted(impacted))
