"""Tests for APIX-2.2 Governance Intelligence: policy signal classifier, lead-lag,
HHI concentration, intraday volatility, availability-adjustment, and UDAN monitor."""

import datetime

import pytest

from packages.statistics.availability_index import SCARCITY_BETA, scarcity_premium_pct
from packages.statistics.concentration import ConcentrationService, _share_vector, compute_hhi
from packages.statistics.intraday_volatility import _window_for
from packages.statistics.leading_indicator import (
    _directional_accuracy,
    align_series,
    compute_lead_lag,
    weekly_series,
)
from packages.statistics.policy_signal import classify_elevation

BASE = datetime.date(2026, 10, 1)


def _dates(n, start=BASE):
    return [start + datetime.timedelta(days=i) for i in range(n)]


# --------------------------------------------------------------------------- #
# 1. Policy signal classifier (RBI MPC)
# --------------------------------------------------------------------------- #


def test_policy_signal_no_elevation():
    values = [100.0] * 20 + [101.0, 102.0, 102.5, 101.5, 101.0]
    res = classify_elevation(values=values, dates=_dates(len(values)))
    assert res["mode"] == "NO_ELEVATION"


def test_policy_signal_transient_short_spike():
    # Short-lived, single-carrier, no ATF move -> TRANSIENT
    values = [100.0] * 20 + [120.0, 118.0, 105.0]
    res = classify_elevation(
        values=values,
        dates=_dates(len(values)),
        calendar_dates=set(),
        carrier_breadth=1,
        atf_move_pct=-0.2,
    )
    assert res["mode"] == "TRANSIENT"
    assert res["persistence_days"] <= 14


def test_policy_signal_transient_calendar_aligned():
    values = [100.0] * 20 + [118.0, 122.0, 121.0, 116.0, 112.0]
    dates = _dates(len(values))
    # Festival peak inside the spike window (spike spans dates[20:25])
    spike_start = dates[20] + datetime.timedelta(days=1)
    res = classify_elevation(
        values=values,
        dates=dates,
        calendar_dates={spike_start},
        carrier_breadth=4,
        atf_move_pct=0.0,
    )
    assert res["mode"] == "TRANSIENT"
    assert res["calendar_aligned"] is True
    assert res["transient_score"] > res["structural_score"]


def test_policy_signal_structural_sustained_multicarrier_atf():
    values = [100.0] * 30 + [130.0 + i * 0.2 for i in range(25)]  # 25 days sustained
    res = classify_elevation(
        values=values,
        dates=_dates(len(values)),
        calendar_dates=set(),
        carrier_breadth=4,
        atf_move_pct=2.5,
    )
    assert res["mode"] == "STRUCTURAL"
    assert res["persistence_days"] >= 21
    assert res["multi_carrier"] is True
    assert res["atf_aligned"] is True


# --------------------------------------------------------------------------- #
# 2. Billion-Prices lead-lag
# --------------------------------------------------------------------------- #


def test_weekly_series_aggregates_by_monday():
    # Two Mondays; second week has two points -> averaged
    pairs = [
        (datetime.date(2026, 11, 9), 100.0),   # Monday
        (datetime.date(2026, 11, 16), 110.0),  # Monday
        (datetime.date(2026, 11, 17), 120.0),  # Tuesday
    ]
    out = weekly_series(pairs)
    assert list(out.keys()) == ["2026-11-09", "2026-11-16"]
    assert out["2026-11-16"] == 115.0


def test_align_series_common_keys_only():
    p = {"2026-11-09": 100.0, "2026-11-16": 110.0}
    c = {"2026-11-16": 105.0, "2026-11-23": 108.0}
    aligned = align_series(p, c)
    assert [(k, ) for k, _, _ in aligned] == [("2026-11-16",)]


def test_directional_accuracy_basic():
    assert _directional_accuracy([100, 101, 102], [100, 101, 102]) == 100.0
    # proto diffs [+, -], cpi diffs [+, +] -> 1 of 2 match = 50%
    assert _directional_accuracy([100, 102, 101], [100, 101, 102]) == 50.0


def test_compute_lead_lag_finds_synthetic_lead():
    # Non-monotonic weekly price with a 1-week CPI publication lag, so the
    # prototype genuinely leads by one week (monotonic series are degenerate).
    weeks = ["2026-11-02", "2026-11-09", "2026-11-16", "2026-11-23",
             "2026-11-30", "2026-12-07", "2026-12-14", "2026-12-21"]
    p = [100.0, 105.0, 98.0, 108.0, 102.0, 110.0, 96.0, 112.0]
    proto = dict(zip(weeks, p))
    cpi = {weeks[0]: p[0]}
    for i in range(1, len(weeks)):
        cpi[weeks[i]] = p[i - 1]  # CPI print lags the true price by one week
    res = compute_lead_lag(proto, cpi)
    assert res["status"] == "COMPLETED"
    assert res["best_lag_weeks"] == 1
    assert res["best_lag_pearson_r"] > 0.9


# --------------------------------------------------------------------------- #
# 3. HHI concentration
# --------------------------------------------------------------------------- #


def test_share_vector_and_hhi():
    sv = _share_vector([4, 3, 1])
    assert sum(sv) == pytest.approx(1.0)
    # 8 quotes: 4/3/1 -> shares 0.5/0.375/0.125
    assert compute_hhi(sv) == pytest.approx(4062.5)
    # Full monopoly
    assert compute_hhi([1.0]) == 10000.0


def test_hhi_bands():
    assert ConcentrationService._band(1000.0) == "LOW"
    assert ConcentrationService._band(2000.0) == "MODERATE"
    assert ConcentrationService._band(3000.0) == "HIGH"


# --------------------------------------------------------------------------- #
# 4. Intraday volatility windowing
# --------------------------------------------------------------------------- #


def test_window_for_hours():
    assert _window_for(6) == "MORNING_0600"
    assert _window_for(12) == "NOON_1200"
    assert _window_for(18) == "EVENING_1800"
    assert _window_for(23) == "NIGHT_2300"


# --------------------------------------------------------------------------- #
# 5. Constant sanity
# --------------------------------------------------------------------------- #


def test_availability_beta_in_bounds():
    assert 0.0 < SCARCITY_BETA <= 1.0


def test_scarcity_premium_pct():
    assert scarcity_premium_pct(0.0) == 0.0
    assert scarcity_premium_pct(0.5) == pytest.approx(SCARCITY_BETA * 50.0)
    # saturates at full sell-out
    assert scarcity_premium_pct(2.0) == pytest.approx(SCARCITY_BETA * 100.0)
