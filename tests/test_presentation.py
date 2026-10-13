"""Regression tests for dashboard-friendly scales and charts."""

import numpy as np
import pytest

from fintrace.narrative import ClaimKind, NarrativeClaim, ReviewStatus, review_claim
from fintrace.memory import append_note, read_notes
from fintrace.presentation import histogram_rows, is_repeat_submission, narrative_input_spec


def test_margin_defaults_are_human_readable_percentages():
    spec = narrative_input_spec(ClaimKind.MARGIN_EXPANSION)
    assert spec.earlier is None
    assert (spec.prior, spec.current, spec.divisor) == (20.0, 19.0, 100.0)
    claim = NarrativeClaim("Margins expanded", "Example plc", "p. 3", ClaimKind.MARGIN_EXPANSION)
    review = review_claim(claim, prior_prior=None, prior=spec.prior/spec.divisor,
                          current=spec.current/spec.divisor)
    assert review.status is ReviewStatus.TENSION
    assert review.metric_before == pytest.approx(.20)


def test_revenue_acceleration_requires_three_periods():
    spec = narrative_input_spec(ClaimKind.REVENUE_ACCELERATION)
    assert spec.earlier == 100.0
    assert spec.prior == 120.0
    assert spec.current == 140.0


def test_monte_carlo_histogram_is_continuous_and_accounts_for_each_sample():
    samples = np.array([-250.0, 15.0, 15.0, 15.0, 1900.0, 3000.0])
    rows = histogram_rows(samples, bins=4)
    assert len(rows) == 4
    assert sum(r["frequency"] for r in rows) == len(samples)
    assert all(rows[i]["upper"] == rows[i+1]["lower"] for i in range(3))
    assert rows[0]["lower"] <= samples.min()
    assert rows[-1]["upper"] >= samples.max()


@pytest.mark.parametrize("samples, bins", [([], 4), ([1, float('nan')], 4), ([1], 1)])
def test_histogram_rejects_bad_inputs(samples, bins):
    with pytest.raises(ValueError):
        histogram_rows(samples, bins=bins)


def test_analyst_journal_blocks_only_immediate_exact_duplicate(tmp_path):
    path = tmp_path / "journal.jsonl"
    fields = dict(analyst="Analyst", subject="EBIT margin", prior_assumption="20%",
                  revised_assumption="19%", rationale="Higher expected costs",
                  evidence_reference="Board report p.3")
    assert not is_repeat_submission(read_notes(path), **fields)
    append_note(path, **fields)
    assert is_repeat_submission(read_notes(path), **fields)
    assert not is_repeat_submission(read_notes(path), **(fields | {"rationale": "Updated evidence"}))
