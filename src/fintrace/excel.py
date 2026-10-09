"""Excel ingestion for FinTrace.

This module maps a workbook into a transparent, inspectable model snapshot. It does not
attempt to decide which assumptions are "correct". Candidate roles are heuristic hints
for an analyst to review.
"""
from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from openpyxl import load_workbook
from openpyxl.formula import Tokenizer
from openpyxl.utils import get_column_letter, range_boundaries
from pydantic import BaseModel, ConfigDict, Field


CELL_REF_RE = re.compile(r"^\$?[A-Z]{1,3}\$?\d+$", re.IGNORECASE)
RANGE_REF_RE = re.compile(
    r"^(?:(?P<sheet>'(?:[^']|'')+'|[^!]+)!)?(?P<range>\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)$",
    re.IGNORECASE,
)
ASSUMPTION_KEYWORDS = {
    "assumption", "growth", "margin", "rate", "wacc", "tax", "price", "volume",
    "capex", "days", "turnover", "inflation", "discount", "terminal", "yield",
}
OUTPUT_KEYWORDS = {
    "valuation", "equity value", "enterprise value", "target price", "share price",
    "free cash flow", "fcf", "ebitda", "ebit", "eps", "nopat", "revenue",
}


class ExcelModelError(ValueError):
    """Raised when a workbook cannot be mapped safely."""


class CellSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: str
    sheet: str
    coordinate: str
    value: Any | None = None
    formula: str | None = None
    cached_value: Any | None = None
    number_format: str | None = None
    label: str | None = None
    named_ranges: tuple[str, ...] = ()


class Dependency(BaseModel):
    model_config = ConfigDict(frozen=True)

    upstream: str
    downstream: str
    relation: str = "feeds"


class NamedRangeSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    destinations: tuple[str, ...]


class CandidateRole(BaseModel):
    model_config = ConfigDict(frozen=True)

    ref: str
    role: Literal["assumption", "output"]
    score: float = Field(ge=0.0, le=1.0)
    reasons: tuple[str, ...]


class SheetSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    nonempty_cells: int
    formula_cells: int


class WorkbookSnapshot(BaseModel):
    """A deterministic snapshot of workbook structure and formula lineage."""

    workbook_name: str
    source_path: str
    sheets: tuple[SheetSummary, ...]
    cells: dict[str, CellSnapshot]
    dependencies: tuple[Dependency, ...]
    named_ranges: tuple[NamedRangeSnapshot, ...]
    candidates: tuple[CandidateRole, ...]
    warnings: tuple[str, ...] = ()

    def save_json(self, path: str | Path) -> None:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.model_dump(mode="json"), indent=2, sort_keys=True)
        temporary: str | None = None
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp:
                temporary = temp.name
                temp.write(payload + "\n")
                temp.flush()
                os.fsync(temp.fileno())
            os.replace(temporary, destination)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)


class ExcelIngestor:
    """Read an .xlsx/.xlsm workbook without replacing the analyst's model."""

    def __init__(self, *, max_expanded_range_cells: int = 500) -> None:
        if max_expanded_range_cells < 1:
            raise ValueError("max_expanded_range_cells must be positive")
        self.max_expanded_range_cells = max_expanded_range_cells

    def inspect(self, path: str | Path) -> WorkbookSnapshot:
        source = Path(path)
        if not source.exists():
            raise ExcelModelError(f"Workbook not found: {source}")
        if source.suffix.lower() not in {".xlsx", ".xlsm"}:
            raise ExcelModelError("FinTrace currently supports .xlsx and .xlsm workbooks only.")

        keep_vba = source.suffix.lower() == ".xlsm"
        formulas_wb = load_workbook(source, data_only=False, keep_vba=keep_vba)
        values_wb = load_workbook(source, data_only=True, keep_vba=keep_vba)

        named_ranges, name_to_refs = self._named_ranges(formulas_wb)
        cells: dict[str, CellSnapshot] = {}
        sheet_summaries: list[SheetSummary] = []

        for ws in formulas_wb.worksheets:
            value_ws = values_wb[ws.title]
            nonempty = 0
            formula_count = 0
            for row in ws.iter_rows():
                for cell in row:
                    if cell.value is None:
                        continue
                    nonempty += 1
                    formula = cell.value if isinstance(cell.value, str) and cell.value.startswith("=") else None
                    if formula:
                        formula_count += 1
                    ref = self._qualify(ws.title, cell.coordinate)
                    cells[ref] = CellSnapshot(
                        ref=ref,
                        sheet=ws.title,
                        coordinate=cell.coordinate,
                        value=None if formula else cell.value,
                        formula=formula,
                        cached_value=value_ws[cell.coordinate].value if formula else cell.value,
                        number_format=cell.number_format,
                        label=self._left_label(ws, cell.row, cell.column),
                        named_ranges=tuple(sorted(name_to_refs.get(ref, set()))),
                    )
            sheet_summaries.append(
                SheetSummary(name=ws.title, nonempty_cells=nonempty, formula_cells=formula_count)
            )

        dependencies: list[Dependency] = []
        warnings: list[str] = []
        seen_edges: set[tuple[str, str]] = set()

        for cell in cells.values():
            if not cell.formula:
                continue
            refs, formula_warnings = self._formula_references(
                formula=cell.formula,
                current_sheet=cell.sheet,
                formulas_wb=formulas_wb,
            )
            warnings.extend(f"{cell.ref}: {message}" for message in formula_warnings)
            for upstream in refs:
                edge = (upstream, cell.ref)
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                dependencies.append(Dependency(upstream=upstream, downstream=cell.ref))

        candidates = self._candidates(cells, dependencies)
        return WorkbookSnapshot(
            workbook_name=source.name,
            source_path=str(source.resolve()),
            sheets=tuple(sheet_summaries),
            cells=cells,
            dependencies=tuple(dependencies),
            named_ranges=tuple(named_ranges),
            candidates=tuple(candidates),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    def _named_ranges(self, wb: Any) -> tuple[list[NamedRangeSnapshot], dict[str, set[str]]]:
        snapshots: list[NamedRangeSnapshot] = []
        reverse: dict[str, set[str]] = defaultdict(set)

        for name, defined_name in wb.defined_names.items():
            destinations: list[str] = []
            try:
                for sheet, coord in defined_name.destinations:
                    if ":" in coord:
                        refs, warning = self._expand_reference(sheet, coord)
                        if warning:
                            continue
                        destinations.extend(refs)
                    elif CELL_REF_RE.match(coord.replace("$", "")):
                        destinations.append(self._qualify(sheet, coord))
            except (AttributeError, TypeError, ValueError):
                # Constants, formulas and external names are intentionally retained only
                # as workbook metadata later; they are not safe cell destinations.
                continue

            unique = tuple(dict.fromkeys(destinations))
            if unique:
                snapshots.append(NamedRangeSnapshot(name=name, destinations=unique))
                for ref in unique:
                    reverse[ref].add(name)
        return snapshots, reverse

    def _formula_references(
        self, *, formula: str, current_sheet: str, formulas_wb: Any
    ) -> tuple[list[str], list[str]]:
        refs: list[str] = []
        warnings: list[str] = []
        named = formulas_wb.defined_names

        try:
            items = Tokenizer(formula).items
        except Exception as exc:  # malformed formulas should not stop workbook inspection
            return [], [f"formula could not be tokenized ({exc})"]

        for token in items:
            if token.type != "OPERAND" or token.subtype != "RANGE":
                continue
            raw = token.value.strip()

            match = RANGE_REF_RE.match(raw)
            if match:
                sheet_token = match.group("sheet")
                sheet = self._normalise_sheet(sheet_token) if sheet_token else current_sheet
                expanded, warning = self._expand_reference(sheet, match.group("range"))
                refs.extend(expanded)
                if warning:
                    warnings.append(warning)
                continue

            # A RANGE token can also be a workbook-defined name.
            try:
                defined = named.get(raw)
            except Exception:
                defined = None
            if defined is not None:
                try:
                    for sheet, coord in defined.destinations:
                        expanded, warning = self._expand_reference(sheet, coord)
                        refs.extend(expanded)
                        if warning:
                            warnings.append(f"named range {raw}: {warning}")
                except (AttributeError, TypeError, ValueError):
                    warnings.append(f"named range '{raw}' is not a simple cell/range reference")
                continue

            # Table references, external links and functions such as OFFSET are left
            # unresolved rather than guessed.
            warnings.append(f"unresolved reference token '{raw}'")

        return list(dict.fromkeys(refs)), warnings

    def _expand_reference(self, sheet: str, coord_or_range: str) -> tuple[list[str], str | None]:
        clean = coord_or_range.replace("$", "")
        if ":" not in clean:
            if not CELL_REF_RE.match(clean):
                return [], f"unsupported cell reference '{coord_or_range}'"
            return [self._qualify(sheet, clean)], None

        try:
            min_col, min_row, max_col, max_row = range_boundaries(clean)
        except ValueError:
            return [], f"unsupported range '{coord_or_range}'"

        count = (max_col - min_col + 1) * (max_row - min_row + 1)
        if count > self.max_expanded_range_cells:
            return [], (
                f"range '{coord_or_range}' has {count} cells and exceeds the "
                f"expansion limit of {self.max_expanded_range_cells}"
            )

        refs = [
            self._qualify(sheet, f"{get_column_letter(col)}{row}")
            for row in range(min_row, max_row + 1)
            for col in range(min_col, max_col + 1)
        ]
        return refs, None

    def _candidates(
        self, cells: dict[str, CellSnapshot], dependencies: list[Dependency]
    ) -> list[CandidateRole]:
        downstream_count: dict[str, int] = defaultdict(int)
        incoming_count: dict[str, int] = defaultdict(int)
        for edge in dependencies:
            downstream_count[edge.upstream] += 1
            incoming_count[edge.downstream] += 1

        candidates: list[CandidateRole] = []
        for ref, cell in cells.items():
            label_text = " ".join(
                part for part in [cell.label, *cell.named_ranges] if part
            ).lower()

            if cell.formula is None and isinstance(cell.value, (int, float)) and downstream_count[ref] > 0:
                score = 0.35
                reasons = [f"referenced by {downstream_count[ref]} formula cell(s)"]
                if any(keyword in label_text for keyword in ASSUMPTION_KEYWORDS):
                    score += 0.25
                    reasons.append("label/name resembles a modelling assumption")
                if cell.number_format and "%" in cell.number_format:
                    score += 0.15
                    reasons.append("percentage-formatted input")
                if cell.named_ranges:
                    score += 0.15
                    reasons.append("cell has a workbook-defined name")
                if downstream_count[ref] >= 2:
                    score += 0.10
                    reasons.append("input influences multiple formula cells")
                candidates.append(
                    CandidateRole(ref=ref, role="assumption", score=round(min(score, 1.0), 2), reasons=tuple(reasons))
                )

            if cell.formula is not None:
                score = 0.10
                reasons: list[str] = []
                if downstream_count[ref] == 0:
                    score += 0.35
                    reasons.append("formula result is not consumed by another mapped formula")
                if any(keyword in label_text for keyword in OUTPUT_KEYWORDS):
                    score += 0.35
                    reasons.append("label/name resembles a material financial output")
                if cell.named_ranges:
                    score += 0.10
                    reasons.append("cell has a workbook-defined name")
                if incoming_count[ref] >= 2:
                    score += 0.10
                    reasons.append("output combines multiple upstream inputs")
                if score >= 0.45:
                    candidates.append(
                        CandidateRole(ref=ref, role="output", score=round(min(score, 1.0), 2), reasons=tuple(reasons))
                    )

        return sorted(candidates, key=lambda candidate: (-candidate.score, candidate.role, candidate.ref))

    @staticmethod
    def _normalise_sheet(sheet: str) -> str:
        sheet = sheet.strip()
        if sheet.startswith("'") and sheet.endswith("'"):
            sheet = sheet[1:-1].replace("''", "'")
        return sheet

    @staticmethod
    def _qualify(sheet: str, coordinate: str) -> str:
        clean = coordinate.replace("$", "")
        escaped = sheet.replace("'", "''")
        return f"'{escaped}'!{clean}"

    @staticmethod
    def _left_label(ws: Any, row: int, column: int) -> str | None:
        # Financial models commonly place row labels immediately to the left. Search
        # up to two columns left and preserve only text labels.
        for offset in (1, 2):
            col = column - offset
            if col < 1:
                break
            value = ws.cell(row=row, column=col).value
            if isinstance(value, str) and not value.startswith("=") and value.strip():
                return value.strip()
        return None
