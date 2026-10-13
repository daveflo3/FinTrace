"""Local append-only analyst reasoning journal; explicit entries, no inferred intent."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class AnalystNote:
    id: str
    recorded_at: str
    analyst: str
    subject: str
    prior_assumption: str
    revised_assumption: str
    rationale: str
    evidence_reference: str


def append_note(path: str | Path, *, analyst: str, subject: str,
                prior_assumption: str, revised_assumption: str,
                rationale: str, evidence_reference: str) -> AnalystNote:
    """Never replaces previous revisions; keeps entries on the user's local machine."""
    if not all(x.strip() for x in (analyst, subject, rationale, revised_assumption, evidence_reference)):
        raise ValueError("Analyst, subject, revised assumption, rationale and evidence reference required.")
    note = AnalystNote(
        id=str(uuid4()), recorded_at=datetime.now(timezone.utc).isoformat(),
        analyst=analyst, subject=subject, prior_assumption=prior_assumption,
        revised_assumption=revised_assumption, rationale=rationale,
        evidence_reference=evidence_reference,
    )
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(asdict(note), ensure_ascii=False) + "\n")
    return note


def read_notes(path: str | Path) -> list[AnalystNote]:
    source = Path(path)
    if not source.exists():
        return []
    notes = []
    for line_no, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            notes.append(AnalystNote(**json.loads(line)))
        except (TypeError, ValueError) as e:
            raise ValueError(f"Invalid journal entry at line {line_no}: {e}") from e
    return notes
