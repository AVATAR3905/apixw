"""Unit tests for the Phase 4 IQR/MAD anomaly detector."""

import datetime

import numpy as np

from packages.statistics.anomaly_detector import (
    AnomalyHit,
    detect_on_values,
    escalate_hits,
)


def _d(offset: int):
    base = datetime.date(2026, 8, 1)
    return base + datetime.timedelta(days=offset)


def test_detect_on_values_clean_series_no_hits():
    values = [100.0 + i for i in range(20)]  # smooth linear climb
    rep = detect_on_values(values, anomaly_type="INDEX_SPIKE")
    assert rep.total_points == 20
    assert rep.hits == []


def test_detect_spike_with_mad_and_iqr():
    # Noisy baseline around 100-102, then a single 160 spike
    values = ([100.0, 101.0, 102.0] * 12) + [160.0]
    rep = detect_on_values(values, anomaly_type="INDEX_SPIKE")
    assert len(rep.hits) == 1
    hit = rep.hits[0]
    assert hit.value == 160.0
    assert hit.severity == "SEVERE"
    assert hit.anomaly_type == "INDEX_SPIKE"
    assert abs(hit.z_score) >= 5.0
    assert hit.reference_median == 101.0


def test_flat_series_spike_caught_by_iqr_fence():
    # Degenerate MAD (all-100 baseline) hides the z-score, but the IQR outer
    # fence must still catch the 160 spike.
    values = [100.0] * 25 + [160.0] + [100.0] * 9
    rep = detect_on_values(values, anomaly_type="INDEX_SPIKE")
    assert len(rep.hits) == 1
    hit = rep.hits[0]
    assert hit.severity == "SEVERE"
    assert hit.iqr_outer_breach is True
    assert hit.reference_median == 100.0


def test_mild_deviation_classified_low_or_none():
    # Seasonally repeating pattern 95..110 — no point should breach fences/z
    values = [95.0, 100.0, 105.0, 110.0, 98.0, 102.0, 108.0] * 5
    rep = detect_on_values(values)
    assert rep.total_points == 35
    assert rep.hits == []


def test_escalation_requires_severe_or_consecutive():
    spike_hits = [
        AnomalyHit(
            observation_date=_d(5), value=160.0, reference_median=100.0, z_score=6.0,
            iqr_inner_breach=True, iqr_outer_breach=True, severity="SEVERE",
            anomaly_type="INDEX_SPIKE",
        )
    ]
    rep = escalate_hits(spike_hits, anomaly_type="INDEX_SPIKE")
    assert rep.is_escalated is True
    assert rep.max_severity == "SEVERE"
    assert "severe" in rep.escalation_reason

    # Two consecutive LOW hits alone do NOT escalate
    low_hits = [
        AnomalyHit(
            observation_date=_d(1), value=105.0, reference_median=100.0, z_score=2.8,
            iqr_inner_breach=True, iqr_outer_breach=False, severity="LOW",
            anomaly_type="PRICE_OUTLIER",
        ),
        AnomalyHit(
            observation_date=_d(2), value=106.0, reference_median=100.0, z_score=3.0,
            iqr_inner_breach=True, iqr_outer_breach=False, severity="LOW",
            anomaly_type="PRICE_OUTLIER",
        ),
    ]
    rep = escalate_hits(low_hits, anomaly_type="PRICE_OUTLIER", consecutive_threshold=2)
    assert rep.is_escalated is False

    # Two consecutive MODERATE hits DO escalate
    mod_hits = [
        AnomalyHit(
            observation_date=_d(1), value=115.0, reference_median=100.0, z_score=4.0,
            iqr_inner_breach=True, iqr_outer_breach=False, severity="MODERATE",
            anomaly_type="INDEX_SPIKE",
        ),
        AnomalyHit(
            observation_date=_d(2), value=116.0, reference_median=100.0, z_score=4.2,
            iqr_inner_breach=True, iqr_outer_breach=False, severity="MODERATE",
            anomaly_type="INDEX_SPIKE",
        ),
    ]
    rep = escalate_hits(mod_hits, anomaly_type="INDEX_SPIKE")
    assert rep.is_escalated is True
    assert rep.consecutive_count == 2


def test_escalate_empty_report():
    rep = escalate_hits([], anomaly_type="PRICE_OUTLIER")
    assert rep.is_escalated is False
    assert rep.total_hits == 0


def test_mad_filter_matches_estimator_behavior():
    """The detector's MAD z-scores should agree with the estimator outlier filter."""
    from packages.statistics.estimators import _mad_based_outlier_filter

    values = np.array(([100.0, 101.0, 102.0] * 10) + [150.0] + [101.0, 100.0])
    filtered = _mad_based_outlier_filter(values)
    # Estimator drops the 150 spike (32 -> 31 values); detector flags the same point
    assert len(filtered) == len(values) - 1
    assert 150.0 not in filtered
    rep = detect_on_values(list(values))
    assert any(h.value == 150.0 for h in rep.hits)
