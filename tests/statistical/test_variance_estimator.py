"""Deterministic tests for the bootstrap/jackknife index variance estimators."""

import numpy as np
import pytest

from packages.statistics.index_engine import AirfareIndexEngine
from packages.statistics.variance import (
    IndexVarianceError,
    IndexVarianceEstimator,
    _norm_ppf,
)


def test_norm_ppf_reference_values():
    """Acklam quantile function matches known normal quantiles within 1e-3."""
    assert _norm_ppf(0.5) == pytest.approx(0.0, abs=1e-6)
    assert _norm_ppf(0.975) == pytest.approx(1.95996398, abs=1e-3)
    assert _norm_ppf(0.025) == pytest.approx(-1.95996398, abs=1e-3)
    assert _norm_ppf(0.95) == pytest.approx(1.64485362, abs=1e-3)


def test_bootstrap_se_positive_with_dispersion():
    """Varying carrier fares within cells must produce a positive SE."""
    samples = {
        "A": [1000.0, 1200.0, 1400.0, 1600.0, 1100.0, 1500.0],
        "B": [2000.0, 2400.0, 2200.0, 2600.0],
    }
    base = {"A": 1200.0, "B": 2300.0}
    weights = {"A": 0.6, "B": 0.4}

    result = IndexVarianceEstimator.bootstrap_index_variance(
        samples, base, weights, observed_index=100.0, n_bootstrap=4000, random_seed=42
    )
    assert result["standard_error"] > 0
    assert result["ci_lower"] < 100.0 < result["ci_upper"]
    assert result["n_bootstrap"] == 4000
    assert result["method"].startswith("BOOTSTRAP_PERCENTILE")
    assert result["ci_normal_lower"] < result["ci_normal_upper"]


def test_bootstrap_ci_contains_engine_index():
    """The bootstrap CI must bracket the deterministic Laspeyres value."""
    samples = {
        "A": [100.0, 105.0, 115.0, 95.0],
        "B": [200.0, 210.0, 190.0],
        "C": [150.0, 160.0, 155.0, 145.0, 165.0],
    }
    base = {"A": 100.0, "B": 200.0, "C": 150.0}
    weights = {"A": 0.5, "B": 0.3, "C": 0.2}

    observed = AirfareIndexEngine.calculate_national_index(
        route_prices={r: np.mean(v) for r, v in samples.items()},
        base_prices=base,
        route_weights=weights,
    )["index_value"]

    result = IndexVarianceEstimator.bootstrap_index_variance(
        samples, base, weights, observed_index=observed, n_bootstrap=5000, random_seed=7
    )
    assert result["ci_lower"] <= observed <= result["ci_upper"]
    assert result["bias"] == pytest.approx(result["mean_index"] - observed, abs=1e-3)


def test_bootstrap_se_increases_with_dispersion():
    """Wider within-cell dispersion widens the index CI (monotonic)."""
    tight = {
        "A": [100.0, 101.0, 100.5, 100.2, 99.8],
        "B": [200.0, 201.0, 200.5, 199.5],
    }
    wide = {
        "A": [100.0, 190.0, 60.0, 150.0, 120.0],
        "B": [200.0, 310.0, 120.0, 250.0],
    }
    base = {"A": 100.0, "B": 200.0}
    weights = {"A": 0.6, "B": 0.4}

    se_tight = IndexVarianceEstimator.bootstrap_index_variance(
        tight, base, weights, n_bootstrap=3000, random_seed=1
    )["standard_error"]
    se_wide = IndexVarianceEstimator.bootstrap_index_variance(
        wide, base, weights, n_bootstrap=3000, random_seed=1
    )["standard_error"]
    assert se_wide > se_tight


def test_bootstrap_single_constant_cell_zero_se():
    """A single unattributed value yields zero sampling variance."""
    samples = {"A": [1000.0, 1000.0, 1000.0]}
    base = {"A": 1000.0}
    weights = {"A": 1.0}
    result = IndexVarianceEstimator.bootstrap_index_variance(
        samples, base, weights, observed_index=100.0, n_bootstrap=2000, random_seed=3
    )
    assert result["standard_error"] == pytest.approx(0.0, abs=1e-9)
    assert result["ci_lower"] == pytest.approx(100.0, abs=1e-6)


def test_bootstrap_requires_valid_route():
    """Degenerate inputs (no valid samples/base) raise IndexVarianceError."""
    with pytest.raises(IndexVarianceError):
        IndexVarianceEstimator.bootstrap_index_variance({}, {}, {}, n_bootstrap=100)


def test_bootstrap_rejects_degenerate_replication_count():
    """n_bootstrap < 2 must fail fast instead of emitting NaNs."""
    samples = {"A": [100.0, 120.0], "B": [200.0, 220.0]}
    base = {"A": 100.0, "B": 200.0}
    weights = {"A": 0.6, "B": 0.4}
    for bad in (0, 1, -5, 2.5, "100"):
        with pytest.raises(IndexVarianceError):
            IndexVarianceEstimator.bootstrap_index_variance(
                samples, base, weights, n_bootstrap=bad
            )


def test_bootstrap_rejects_invalid_confidence_level():
    """Confidence levels outside (0, 1) are rejected up front."""
    samples = {"A": [100.0, 120.0], "B": [200.0, 220.0]}
    base = {"A": 100.0, "B": 200.0}
    weights = {"A": 0.6, "B": 0.4}
    for bad in (0.0, 1.0, 1.5, -0.1):
        with pytest.raises(IndexVarianceError):
            IndexVarianceEstimator.bootstrap_index_variance(
                samples, base, weights, confidence_level=bad
            )
    # 0.5 is a legitimate (if unusual) 50% confidence interval
    IndexVarianceEstimator.bootstrap_index_variance(
        samples, base, weights, confidence_level=0.5
    )


def test_route_bootstrap_rejects_degenerate_params():
    """Route-level estimator shares the same validation layer."""
    with pytest.raises(IndexVarianceError):
        IndexVarianceEstimator.bootstrap_route_index_variance(
            [100.0, 120.0], base_price=100.0, n_bootstrap=1
        )
    with pytest.raises(IndexVarianceError):
        IndexVarianceEstimator.bootstrap_route_index_variance(
            [100.0, 120.0], base_price=100.0, confidence_level=1.0
        )


def test_ci_always_brackets_observed_index():
    """Even a degenerate (zero-variance) cell must yield a CI containing the
    published point -- the percentile band is clamped to the rounded index."""
    samples = {"A": [1000.0, 1000.0, 1000.0], "B": [2000.0, 2000.0, 2000.0]}
    base = {"A": 1000.0, "B": 2000.0}
    weights = {"A": 0.6, "B": 0.4}

    # observed_index deliberately differs from the resample mean by rounding
    result = IndexVarianceEstimator.bootstrap_index_variance(
        samples, base, weights, observed_index=129.42, n_bootstrap=2000, random_seed=1
    )
    assert result["ci_lower"] <= 129.42 <= result["ci_upper"]

    route_result = IndexVarianceEstimator.bootstrap_route_index_variance(
        [1000.0, 1000.0, 1000.0], base_price=1000.0, observed_index=100.13,
        n_bootstrap=2000, random_seed=1,
    )
    assert route_result["ci_lower"] <= 100.13 <= route_result["ci_upper"]


def test_bootstrap_is_deterministic_with_seed():
    """Same seed reproduces identical bootstrap statistics."""
    samples = {"A": [100.0, 130.0, 90.0, 110.0], "B": [200.0, 230.0, 180.0]}
    base = {"A": 100.0, "B": 200.0}
    weights = {"A": 0.6, "B": 0.4}

    r1 = IndexVarianceEstimator.bootstrap_index_variance(
        samples, base, weights, n_bootstrap=2000, random_seed=11
    )
    r2 = IndexVarianceEstimator.bootstrap_index_variance(
        samples, base, weights, n_bootstrap=2000, random_seed=11
    )
    assert r1 == r2


def test_route_index_variance_positive():
    """Route-level bootstrap produces a CI around the route index."""
    result = IndexVarianceEstimator.bootstrap_route_index_variance(
        route_sample=[4000.0, 4200.0, 3900.0, 4600.0, 4050.0],
        base_price=4100.0,
        observed_index=100.0,
        n_bootstrap=4000,
        random_seed=5,
    )
    assert result["standard_error"] > 0
    assert result["ci_lower"] < 100.0 < result["ci_upper"]


def test_jackknife_known_index():
    """
    Routes A/B/C with weights 0.6/0.3/0.1 and relatives 1.0/1.2/1.1:
    I = 100 * (0.6*1.0 + 0.3*1.2 + 0.1*1.1) = 107.0.
    Dropping A re-normalises B/C weights to 0.75/0.25 -> I_(-A) = 117.5,
    so contribution_A = 107.0 - 117.5 = -10.5.
    """
    prices = {"A": 100.0, "B": 120.0, "C": 110.0}
    base = {"A": 100.0, "B": 100.0, "C": 100.0}
    weights = {"A": 0.6, "B": 0.3, "C": 0.1}

    result = IndexVarianceEstimator.jackknife_index_variance(prices, base, weights)
    assert result["index_value"] == pytest.approx(107.0, abs=1e-6)
    assert result["route_contributions"]["A"] == pytest.approx(-10.5, abs=1e-4)
    assert result["standard_error"] > 0
    assert len(result["route_contributions"]) == 3


def test_jackknife_zero_variance_for_flat_index():
    """When every route relative equals 1.0 the index has zero jackknife variance."""
    prices = {"A": 100.0, "B": 100.0, "C": 100.0, "D": 100.0}
    base = {"A": 100.0, "B": 100.0, "C": 100.0, "D": 100.0}
    weights = {"A": 0.4, "B": 0.3, "C": 0.2, "D": 0.1}

    result = IndexVarianceEstimator.jackknife_index_variance(prices, base, weights)
    assert result["standard_error"] == pytest.approx(0.0, abs=1e-9)
    assert result["index_value"] == pytest.approx(100.0, abs=1e-9)


def test_jackknife_requires_two_routes():
    with pytest.raises(IndexVarianceError):
        IndexVarianceEstimator.jackknife_index_variance(
            {"A": 100.0}, {"A": 100.0}, {"A": 1.0}
        )


def test_coverage_of_population_index():
    """Bootstrap percentile CIs must contain the true population index near
    the nominal 95% rate across repeated simulated days."""
    rng = np.random.default_rng(2026)
    hits = 0
    n_cases = 40
    for _ in range(n_cases):
        pop_a = 100.0
        pop_b = 180.0
        samples = {
            # 20-carrier cells; lognormal noise around the population level
            "A": list(pop_a * rng.lognormal(0.0, 0.10, size=20)),
            "B": list(pop_b * rng.lognormal(0.0, 0.10, size=20)),
        }
        base = {"A": pop_a, "B": pop_b}
        weights = {"A": 0.6, "B": 0.4}
        true_index = 100.0  # population relatives equal the base

        res = IndexVarianceEstimator.bootstrap_index_variance(
            samples, base, weights, n_bootstrap=400, random_seed=2026
        )
        if res["ci_lower"] <= true_index <= res["ci_upper"]:
            hits += 1
    # 95% nominal interval should be calibred to within generous sampling error
    assert hits >= 0.80 * n_cases
