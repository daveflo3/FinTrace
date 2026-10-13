"""Transparent illustrative five-year DCF and exact small-driver Shapley attribution.

This is a self-contained DCF scenario, NOT an evaluator of arbitrary Excel formulas.
All monetary inputs and outputs are in the same user-chosen units (e.g. GBP millions).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from itertools import permutations
from math import factorial, isfinite
from typing import Mapping


DRIVERS = ("revenue_growth", "ebit_margin", "wacc", "terminal_growth")
LABELS = {
    "revenue_growth": "Revenue growth",
    "ebit_margin": "EBIT margin",
    "wacc": "WACC",
    "terminal_growth": "Terminal growth",
}


@dataclass(frozen=True)
class DCFInputs:
    base_revenue: float = 850.0
    revenue_growth: float = 0.08
    ebit_margin: float = 0.20
    tax_rate: float = 0.25
    depreciation_ratio: float = 0.04
    capex_ratio: float = 0.05
    nwc_ratio: float = 0.10
    wacc: float = 0.10
    terminal_growth: float = 0.025
    net_debt: float = 250.0
    years: int = 5

    def validate(self) -> None:
        numbers = [getattr(self, field) for field in self.__dataclass_fields__ if field != "years"]
        if not all(isfinite(v) for v in numbers):
            raise ValueError("All DCF inputs must be finite.")
        if not 1 <= self.years <= 20:
            raise ValueError("Forecast horizon must be between 1 and 20 years.")
        if self.base_revenue <= 0 or self.revenue_growth <= -1:
            raise ValueError("Revenue must be positive and growth greater than -100%.")
        for field in ("ebit_margin", "tax_rate", "depreciation_ratio", "capex_ratio", "nwc_ratio"):
            if not 0 <= getattr(self, field) <= 1:
                raise ValueError(f"{field} must be in [0,1].")
        if not 0 < self.wacc < 1 or not -1 < self.terminal_growth < self.wacc:
            raise ValueError("Require 0 < WACC < 100% and -100% < terminal growth < WACC.")


@dataclass(frozen=True)
class DCFResult:
    enterprise_value: float
    equity_value: float
    pv_explicit_fcf: float
    pv_terminal_value: float
    yearly_fcf: tuple[float, ...]
    yearly_revenue: tuple[float, ...]


def calculate_dcf(inputs: DCFInputs) -> DCFResult:
    """FCF = EBIT*(1-tax) + D&A - capex - change in NWC; fixed margins/ratios."""
    inputs.validate()
    revenues = []
    fcfs = []
    rev = inputs.base_revenue
    pv_fcfs = 0.0
    for year in range(1, inputs.years + 1):
        next_rev = rev * (1 + inputs.revenue_growth)
        ebit = next_rev * inputs.ebit_margin
        fcf = (ebit * (1 - inputs.tax_rate)
               + next_rev * inputs.depreciation_ratio
               - next_rev * inputs.capex_ratio
               - (next_rev - rev) * inputs.nwc_ratio)
        revenues.append(next_rev)
        fcfs.append(fcf)
        pv_fcfs += fcf / (1 + inputs.wacc) ** year
        rev = next_rev
    terminal_fcf = fcfs[-1] * (1 + inputs.terminal_growth)
    terminal_value = terminal_fcf / (inputs.wacc - inputs.terminal_growth)
    pv_terminal = terminal_value / (1 + inputs.wacc) ** inputs.years
    ev = pv_fcfs + pv_terminal
    return DCFResult(ev, ev - inputs.net_debt, pv_fcfs, pv_terminal,
                     tuple(fcfs), tuple(revenues))


@dataclass(frozen=True)
class AttributionResult:
    old_equity_value: float
    new_equity_value: float
    total_change: float
    contributions: Mapping[str, float]
    explanation: str = "Exact Shapley allocation across four changed inputs of this illustrative DCF only."


def attribute_dcf_change(old: DCFInputs, new: DCFInputs) -> AttributionResult:
    """Average marginal contribution across the 4! paths; no unexplained residual.

    To avoid a misleading attribution, non-driver inputs must be identical.
    This is not attribution of arbitrary Excel workbooks.
    """
    old.validate()
    new.validate()
    for field in old.__dataclass_fields__:
        if field not in DRIVERS and getattr(old, field) != getattr(new, field):
            raise ValueError(f"Non-attributed parameter changed: {field}. Keep fixed inputs equal.")
    contributions = dict.fromkeys(DRIVERS, 0.0)
    for ordering in permutations(DRIVERS):
        state = old
        last_value = calculate_dcf(state).equity_value
        for driver in ordering:
            state = replace(state, **{driver: getattr(new, driver)})
            current_value = calculate_dcf(state).equity_value
            contributions[driver] += current_value - last_value
            last_value = current_value
    n_paths = factorial(len(DRIVERS))
    contributions = {k: v / n_paths for k, v in contributions.items()}
    old_value = calculate_dcf(old).equity_value
    new_value = calculate_dcf(new).equity_value
    return AttributionResult(old_value, new_value, new_value - old_value, contributions)
