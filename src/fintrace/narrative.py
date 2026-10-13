"""Rule-based checks of source-attributed claims vs analyst-supplied numbers.

The module never asserts that management misled investors. It raises review
questions with explicit thresholds and limitations; no LLM extraction assumed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite


class ClaimKind(StrEnum):
    MARGIN_EXPANSION = "margin_expansion"
    REVENUE_ACCELERATION = "revenue_acceleration"
    CASH_FLOW_IMPROVEMENT = "cash_flow_improvement"


class ReviewStatus(StrEnum):
    ALIGNED = "aligned"
    TENSION = "tension"
    INSUFFICIENT = "insufficient_data"


@dataclass(frozen=True)
class NarrativeClaim:
    statement: str
    source: str
    source_location: str
    kind: ClaimKind


@dataclass(frozen=True)
class NarrativeReview:
    status: ReviewStatus
    question: str
    metric_before: float | None
    metric_after: float | None
    disclaimer: str = "Rule-based comparison; not a factual verdict or allegation."


def review_claim(claim: NarrativeClaim, *, prior_prior: float | None,
                 prior: float | None, current: float | None,
                 tolerance: float = 1e-9) -> NarrativeReview:
    if not claim.statement.strip() or not claim.source.strip() or not claim.source_location.strip():
        raise ValueError("Claim text, source and precise source location are required.")
    if tolerance < 0 or not isfinite(tolerance):
        raise ValueError("Tolerance must be finite and nonnegative.")
    if prior is None or current is None or (claim.kind is ClaimKind.REVENUE_ACCELERATION and prior_prior is None):
        return NarrativeReview(ReviewStatus.INSUFFICIENT, "Add enough comparable periods before assessing the claim.", None, None)
    vals = [v for v in (prior_prior, prior, current) if v is not None]
    if not all(isfinite(v) for v in vals):
        raise ValueError("All supplied financial values must be finite.")
    if claim.kind is ClaimKind.REVENUE_ACCELERATION:
        if prior_prior == 0 or prior == 0:
            return NarrativeReview(ReviewStatus.INSUFFICIENT, "Cannot calculate meaningful growth rates with zero prior revenue.", None, None)
        before = prior / prior_prior - 1
        after = current / prior - 1
        label = "Revenue growth"
    else:
        before, after = prior, current
        label = "EBIT margin" if claim.kind is ClaimKind.MARGIN_EXPANSION else "Cash flow"
    if after > before + tolerance:
        return NarrativeReview(ReviewStatus.ALIGNED, f"{label} increased in the supplied data. Verify source and period comparability.", before, after)
    return NarrativeReview(ReviewStatus.TENSION,
                           f"The claim suggests improvement, but {label.lower()} did not increase in these periods. Ask whether timing, adjustments or definitions explain the difference.",
                           before, after)
