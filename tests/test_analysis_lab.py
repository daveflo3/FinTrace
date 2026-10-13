from dataclasses import replace
from datetime import date

import numpy as np
import pytest

from fintrace.valuation import DCFInputs, calculate_dcf, attribute_dcf_change, DRIVERS
from fintrace.risk import TriangularRange, stress_fragility, monte_carlo
from fintrace.backtest import ForecastObservation, backtest, bias_by_analyst_metric
from fintrace.memory import append_note, read_notes
from fintrace.narrative import ClaimKind, NarrativeClaim, ReviewStatus, review_claim


def test_dcf_components_reconcile():
    result = calculate_dcf(DCFInputs())
    assert result.enterprise_value == pytest.approx(result.pv_explicit_fcf + result.pv_terminal_value)
    assert result.equity_value == pytest.approx(result.enterprise_value - 250)
    assert len(result.yearly_fcf) == 5


def test_dcf_rejects_invalid_assumptions():
    with pytest.raises(ValueError, match="terminal growth"):
        calculate_dcf(DCFInputs(wacc=.04, terminal_growth=.04))
    with pytest.raises(ValueError, match="growth"):
        calculate_dcf(DCFInputs(revenue_growth=-1.01))


def test_shapley_reconciles_exactly():
    old = DCFInputs()
    new = replace(old, revenue_growth=.055, ebit_margin=.18, wacc=.115, terminal_growth=.02)
    r = attribute_dcf_change(old,new)
    assert set(r.contributions) == set(DRIVERS)
    assert sum(r.contributions.values()) == pytest.approx(r.total_change, abs=1e-8)
    assert r.total_change == pytest.approx(calculate_dcf(new).equity_value - calculate_dcf(old).equity_value)


def test_shapley_rejects_untracked_changes():
    with pytest.raises(ValueError, match="Non-attributed"):
        attribute_dcf_change(DCFInputs(), DCFInputs(net_debt=300))


def test_fragility_indicates_downside_concentration_not_probability():
    result = stress_fragility(DCFInputs(), {"revenue_growth": .05, "ebit_margin": .17,
                                             "wacc": .125, "terminal_growth": .015})
    assert all(x >= 0 for x in result.downside_amounts.values())
    assert 0 <= result.largest_two_concentration_pct <= 100
    assert max(result.downside_amounts.values()) > 0


def test_monte_carlo_reproducible_and_ordered():
    ranges = {"revenue_growth":TriangularRange(.03,.08,.12),
              "ebit_margin":TriangularRange(.15,.20,.22),
              "wacc":TriangularRange(.08,.10,.13),
              "terminal_growth":TriangularRange(.015,.025,.035)}
    a = monte_carlo(DCFInputs(),ranges,trials=1000,seed=12)
    b = monte_carlo(DCFInputs(),ranges,trials=1000,seed=12)
    assert np.array_equal(a.samples,b.samples)
    assert a.p05 <= a.p50 <= a.p95
    assert 0 <= a.probability_above_hurdle <= 1


def test_monte_carlo_rejects_invalid_crossed_discount_rates():
    ranges = {"revenue_growth":TriangularRange(.03,.08,.12),
              "ebit_margin":TriangularRange(.15,.20,.22),
              "wacc":TriangularRange(.02,.04,.06),
              "terminal_growth":TriangularRange(.025,.03,.045)}
    with pytest.raises(ValueError, match="below WACC"):
        monte_carlo(DCFInputs(),ranges)


def observation(**kwargs):
    data=dict(analyst="Analyst A",metric="Revenue (GBP m)",
              as_of=date(2022,1,1),target_date=date(2022,12,31),
              actual_released_on=date(2023,2,1),forecast=110,actual=100)
    data.update(kwargs)
    return ForecastObservation(**data)


def test_backtesting_respects_as_of_release_dates():
    rows=[observation(), observation(actual_released_on=date(2024,2,1),actual=95)]
    a=backtest(rows,observed_by=date(2023,5,1))
    assert a.n==1 and a.mean_error==10 and a.wape_pct==pytest.approx(10)
    b=backtest(rows,observed_by=date(2025,1,1))
    assert b.n==2 and b.mean_error==pytest.approx(12.5)


def test_backtesting_no_lookahead():
    with pytest.raises(ValueError,match="target date"):
        backtest([observation(as_of=date(2023,1,1))], observed_by=date(2025,1,1))
    with pytest.raises(ValueError, match="No actual"):
        backtest([observation()],observed_by=date(2022,12,31))


def test_bias_grouped_by_metric_and_analyst():
    rows=[observation(), observation(analyst="B",metric="EPS",forecast=2,actual=3)]
    result=bias_by_analyst_metric(rows,observed_by=date(2024,1,1))
    assert len(result)==2 and result["B | EPS"].mean_error == -1


def test_analyst_memory_append_only(tmp_path):
    path=tmp_path/"notes.jsonl"
    a=append_note(path,analyst="A",subject="margin",prior_assumption="20%",
                  revised_assumption="18%",rationale="Capacity constraints",
                  evidence_reference="2025 report p4")
    b=append_note(path,analyst="A",subject="margin",prior_assumption="18%",
                  revised_assumption="19%",rationale="New guidance",
                  evidence_reference="FY26 update p2")
    rows=read_notes(path)
    assert [r.id for r in rows]==[a.id,b.id]
    assert a.id != b.id


def test_narrative_tension_is_review_question():
    claim=NarrativeClaim("Margins have improved","ExampleCo report","page 6",ClaimKind.MARGIN_EXPANSION)
    answer=review_claim(claim,prior_prior=None,prior=.20,current=.18)
    assert answer.status is ReviewStatus.TENSION
    assert "Ask whether" in answer.question


def test_narrative_acceleration_require_three_periods():
    claim=NarrativeClaim("Growth accelerating","ExampleCo report","page 6",ClaimKind.REVENUE_ACCELERATION)
    assert review_claim(claim,prior_prior=None,prior=100,current=120).status is ReviewStatus.INSUFFICIENT
    assert review_claim(claim,prior_prior=100,prior=120,current=150).status is ReviewStatus.ALIGNED


def test_monte_carlo_zero_uncertainty_matches_dcf():
    inputs=DCFInputs()
    ranges={name:TriangularRange(getattr(inputs,name),getattr(inputs,name),getattr(inputs,name))
            for name in DRIVERS}
    result=monte_carlo(inputs,ranges,trials=200)
    assert result.p05 == pytest.approx(calculate_dcf(inputs).equity_value,abs=1e-8)
    assert result.p95 == pytest.approx(calculate_dcf(inputs).equity_value,abs=1e-8)
