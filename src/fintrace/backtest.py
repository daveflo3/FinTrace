"""Historical forecast evaluation with explicit as-of and observed/release dates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Sequence
from math import isfinite


@dataclass(frozen=True)
class ForecastObservation:
    analyst: str
    metric: str
    as_of: date
    target_date: date
    actual_released_on: date
    forecast: float
    actual: float

    def validate(self) -> None:
        if not self.analyst.strip() or not self.metric.strip():
            raise ValueError("Analyst and metric required.")
        if self.as_of >= self.target_date:
            raise ValueError("Forecast must be issued before its target date.")
        if self.actual_released_on < self.target_date:
            raise ValueError("Actual release date cannot precede its target date.")
        if not all(isfinite(v) for v in (self.forecast, self.actual)):
            raise ValueError("Forecast and actual must be finite.")


@dataclass(frozen=True)
class BacktestSummary:
    n: int
    mean_error: float
    mae: float
    rmse: float
    wape_pct: float | None
    optimistic_count: int
    pessimistic_count: int
    explanation: str = "Error = forecast - actual; positive bias means over-forecasting."


def backtest(rows: Sequence[ForecastObservation], *, observed_by: date) -> BacktestSummary:
    """Only score outcomes actually released by the evaluation date; no lookahead."""
    if not rows:
        raise ValueError("Provide at least one dated historical forecast.")
    for row in rows:
        row.validate()
    eligible = [r for r in rows if r.actual_released_on <= observed_by]
    if not eligible:
        raise ValueError("No actual observations had been released by the evaluation date.")
    errors = [r.forecast - r.actual for r in eligible]
    actual_sum = sum(abs(r.actual) for r in eligible)
    wape = 100 * sum(abs(e) for e in errors) / actual_sum if actual_sum else None
    return BacktestSummary(
        n=len(eligible), mean_error=mean(errors), mae=mean(abs(e) for e in errors),
        rmse=(mean(e*e for e in errors)) ** .5, wape_pct=wape,
        optimistic_count=sum(e > 0 for e in errors),
        pessimistic_count=sum(e < 0 for e in errors),
    )


def bias_by_analyst_metric(rows: Sequence[ForecastObservation], *, observed_by: date) -> dict[str, BacktestSummary]:
    """Separate metrics/units; aggregation across unrelated units is misleading."""
    groups: dict[str, list[ForecastObservation]] = {}
    for row in rows:
        row.validate()
        if row.actual_released_on <= observed_by:
            key = f"{row.analyst} | {row.metric}"
            groups.setdefault(key, []).append(row)
    return {key: backtest(group, observed_by=observed_by) for key, group in groups.items()}
