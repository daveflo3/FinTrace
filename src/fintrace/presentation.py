"""Pure presentation helpers for the optional Streamlit dashboard.

Financial calculations remain in the core modules. These functions only
prepare labels, histogram bins and properly scaled UI inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from .narrative import ClaimKind
from .memory import AnalystNote


@dataclass(frozen=True)
class NarrativeInputSpec:
    unit: str
    earlier: float | None
    prior: float
    current: float
    divisor: float = 1.0


def narrative_input_spec(kind: ClaimKind) -> NarrativeInputSpec:
    """User-facing numeric defaults; margins are percentages, not decimals."""
    if kind is ClaimKind.MARGIN_EXPANSION:
        return NarrativeInputSpec(unit="EBIT margin (%)", earlier=None, prior=20.0,
                                  current=19.0, divisor=100.0)
    if kind is ClaimKind.REVENUE_ACCELERATION:
        return NarrativeInputSpec(unit="Revenue (£m)", earlier=100.0, prior=120.0,
                                  current=140.0)
    if kind is ClaimKind.CASH_FLOW_IMPROVEMENT:
        return NarrativeInputSpec(unit="Cash flow (£m)", earlier=None, prior=100.0,
                                  current=120.0)
    raise ValueError(f"Unsupported narrative claim kind: {kind}")


def histogram_rows(values: Iterable[float], *, bins: int = 32) -> list[dict[str, float | int]]:
    """Return contiguous, human-readable financial value bins for charting.

    The chart uses continuous numeric X coordinates rather than hundreds of
    individual raw sample labels on the horizontal axis.
    """
    samples = np.asarray(list(values), dtype=float)
    if not 2 <= bins <= 100:
        raise ValueError("bins must be between 2 and 100")
    if samples.size == 0 or not np.isfinite(samples).all():
        raise ValueError("values must be nonempty and finite")
    counts, edges = np.histogram(samples, bins=bins)
    return [
        {"lower": float(left), "upper": float(right), "frequency": int(count)}
        for left, right, count in zip(edges[:-1], edges[1:], counts)
    ]


def is_repeat_submission(
    notes: Sequence[AnalystNote],
    *, analyst: str, subject: str, prior_assumption: str,
    revised_assumption: str, rationale: str, evidence_reference: str,
) -> bool:
    """Avoid accidentally appending an identical note twice in the UI.

    This only compares the latest note; deliberately revisiting an older
    decision remains possible without rewriting or deleting history.
    """
    if not notes:
        return False
    last = notes[-1]
    return all((
        last.analyst == analyst,
        last.subject == subject,
        last.prior_assumption == prior_assumption,
        last.revised_assumption == revised_assumption,
        last.rationale == rationale,
        last.evidence_reference == evidence_reference,
    ))
