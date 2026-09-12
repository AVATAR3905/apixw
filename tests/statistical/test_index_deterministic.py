"""Deterministic mathematical test suite for AirfareIndexEngine (PRD Section 61)."""

import pytest

from packages.statistics.index_engine import AirfareIndexEngine, IndexCalculationError


def test_deterministic_two_route_laspeyres_index():
    """
    Mathematical proof test from PRD Section 61:
    Route A: weight = 0.6, base = 100, current = 100 -> relative = 1.0
    Route B: weight = 0.4, base = 100, current = 120 -> relative = 1.2

    Expected index = 100 * (0.6 * 1.0 + 0.4 * 1.2) = 100 * (0.6 + 0.48) = 108.000 exactly!
    """
    route_prices = {"ROUTE_A": 100.0, "ROUTE_B": 120.0}
    base_prices = {"ROUTE_A": 100.0, "ROUTE_B": 100.0}
    route_weights = {"ROUTE_A": 0.6, "ROUTE_B": 0.4}

    result = AirfareIndexEngine.calculate_national_index(
        route_prices=route_prices, base_prices=base_prices, route_weights=route_weights
    )

    assert result["index_value"] == 108.0
    assert result["coverage_rate"] == 100.0
    assert result["is_low_coverage"] is False
    assert result["route_indices"]["ROUTE_A"] == 100.0
    assert result["route_indices"]["ROUTE_B"] == 120.0
    assert result["route_contributions"]["ROUTE_A"] == 60.0
    assert result["route_contributions"]["ROUTE_B"] == 48.0


def test_missing_data_coverage_guard_and_reweighting():
    """
    Verifies that when a route is missing:
    1. Coverage rate drops and flags is_low_coverage = True if below 80%.
    2. Missing routes do NOT default to ₹0 (which would artificially deflate the index to 60.0).
    3. Active weights are re-normalized over available routes.
    """
    # 2 routes, but ROUTE_B is missing (None)
    route_prices = {"ROUTE_A": 100.0, "ROUTE_B": None}
    base_prices = {"ROUTE_A": 100.0, "ROUTE_B": 100.0}
    route_weights = {"ROUTE_A": 0.6, "ROUTE_B": 0.4}

    result = AirfareIndexEngine.calculate_national_index(
        route_prices=route_prices, base_prices=base_prices, route_weights=route_weights
    )

    # Coverage is 1 out of 2 = 50%
    assert result["coverage_rate"] == 50.0
    assert result["is_low_coverage"] is True
    # If it defaulted to 0, index would be 60.0. Re-normalized over Route A gives 100.0!
    assert result["index_value"] == 100.0


def test_weights_must_sum_to_one():
    """Weights that do not sum to 1.0 within tolerance raise IndexCalculationError."""
    route_prices = {"ROUTE_A": 100.0}
    base_prices = {"ROUTE_A": 100.0}
    route_weights = {"ROUTE_A": 0.85}  # sum != 1.0

    with pytest.raises(IndexCalculationError) as exc_info:
        AirfareIndexEngine.calculate_national_index(route_prices, base_prices, route_weights)
    assert "weights must sum to 1.0" in str(exc_info.value)


def test_lead_time_elasticity_surge_multiplier():
    """
    Verifies lead-time elasticity curve and surge multiplier calculation:
    T+45 = 4000.0, T+1 = 9800.0 -> Multiplier = 9800 / 4000 = 2.45x
    """
    prices = {
        45: 4000.0,
        30: 4250.0,
        15: 4800.0,
        7: 6100.0,
        1: 9800.0,
    }

    res = AirfareIndexEngine.calculate_lead_time_elasticity(prices)
    assert res["surge_multiplier_t1_t45"] == 2.45
    assert len(res["lead_time_curve"]) == 5
    assert res["lead_time_curve"][0]["advance_days"] == 45
    assert res["lead_time_curve"][-1]["advance_days"] == 1
