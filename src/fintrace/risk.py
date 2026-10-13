"""Analyst-controlled downside concentration and independent triangular Monte Carlo.

Neither risk indicator is an empirical probability unless the supplied distributions
and ranges are calibrated from appropriate evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping
import numpy as np

from .valuation import DCFInputs, DRIVERS, calculate_dcf


@dataclass(frozen=True)
class StressResult:
    base_value: float
    stressed_values: Mapping[str, float]
    downside_amounts: Mapping[str, float]
    largest_two_concentration_pct: float


def stress_fragility(base: DCFInputs, adverse_values: Mapping[str, float]) -> StressResult:
    """One-variable-at-a-time stressed equity values and *concentration* of downside.

    This is not a probability, nor an overall investment risk score.
    Interactions mean isolated losses cannot be added as a portfolio forecast.
    """
    value = calculate_dcf(base).equity_value
    losses = {}
    stressed = {}
    for field, adverse in adverse_values.items():
        if field not in DRIVERS:
            raise ValueError(f"Unsupported stress driver: {field}")
        result = calculate_dcf(replace(base, **{field: float(adverse)})).equity_value
        stressed[field] = result
        losses[field] = max(0.0, value - result)
    denominator = sum(losses.values())
    concentration = 100 * sum(sorted(losses.values(), reverse=True)[:2]) / denominator if denominator else 0.0
    return StressResult(value, stressed, losses, concentration)


@dataclass(frozen=True)
class TriangularRange:
    low: float
    mode: float
    high: float

    def validate(self) -> None:
        if not (np.isfinite(self.low) and np.isfinite(self.mode) and np.isfinite(self.high)):
            raise ValueError("Simulation bounds must be finite.")
        if not self.low <= self.mode <= self.high:
            raise ValueError("Require low <= most likely <= high for triangular ranges.")


@dataclass(frozen=True)
class MonteCarloResult:
    simulations: int
    seed: int
    p05: float
    p50: float
    p95: float
    mean: float
    probability_above_hurdle: float
    hurdle: float
    samples: np.ndarray
    disclaimer: str = "Illustrative independent input distributions, not empirically calibrated forecasts."


def monte_carlo(
    base: DCFInputs,
    ranges: Mapping[str, TriangularRange],
    *,
    trials: int = 3000,
    seed: int = 42,
    hurdle: float = 0.0,
) -> MonteCarloResult:
    """Independent triangular scenarios. Preserves finance constraints across all samples."""
    base.validate()
    if not 100 <= trials <= 100_000:
        raise ValueError("Simulations must be between 100 and 100,000.")
    if set(ranges) != set(DRIVERS):
        raise ValueError("Provide ranges for revenue_growth, ebit_margin, wacc and terminal_growth.")
    for r in ranges.values():
        r.validate()
    if ranges["revenue_growth"].low <= -1 or not 0 <= ranges["ebit_margin"].low <= ranges["ebit_margin"].high <= 1:
        raise ValueError("Growth must be greater than -100%; EBIT margin in [0,1].")
    if not 0 < ranges["wacc"].low <= ranges["wacc"].high < 1:
        raise ValueError("WACC bounds must be inside (0,1).")
    if ranges["terminal_growth"].low <= -1 or ranges["terminal_growth"].high >= ranges["wacc"].low:
        raise ValueError("Terminal growth's highest bound must be below WACC's lowest bound.")
    if not np.isfinite(hurdle):
        raise ValueError("Hurdle must be finite.")

    rng = np.random.default_rng(seed)
    sampled = {}
    for key in DRIVERS:
        r = ranges[key]
        sampled[key] = (np.full(trials, r.mode, dtype=float)
                        if r.low == r.high else rng.triangular(r.low, r.mode, r.high, size=trials))

    revenue = np.full(trials, base.base_revenue, dtype=float)
    cash_flows = np.zeros(trials, dtype=float)
    for year in range(1, base.years + 1):
        next_rev = revenue * (1 + sampled["revenue_growth"])
        fcf = (next_rev * sampled["ebit_margin"] * (1 - base.tax_rate)
               + next_rev * (base.depreciation_ratio - base.capex_ratio)
               - (next_rev - revenue) * base.nwc_ratio)
        cash_flows += fcf / (1 + sampled["wacc"]) ** year
        revenue = next_rev
    terminal_fcf = fcf * (1 + sampled["terminal_growth"])
    pv_terminal = (terminal_fcf / (sampled["wacc"] - sampled["terminal_growth"]) /
                   (1 + sampled["wacc"]) ** base.years)
    equity = cash_flows + pv_terminal - base.net_debt
    if not np.isfinite(equity).all():
        raise ValueError("Simulation overflow: narrow the model assumptions.")
    p05, p50, p95 = np.percentile(equity, [5, 50, 95])
    return MonteCarloResult(trials, seed, float(p05), float(p50), float(p95),
                            float(equity.mean()), float(np.mean(equity > hurdle)), hurdle, equity)
