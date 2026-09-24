"""Smoke tests for APIX-2.2 Governance & Policy Intelligence endpoints."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_policy_signal_endpoint_smoke():
    res = client.get("/api/v1/analytics/policy-signal")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("COMPLETED", "INSUFFICIENT_DATA")
    if data["status"] == "COMPLETED":
        assert data["classification"] in ("STRUCTURAL", "TRANSIENT", "MIXED", "NO_ELEVATION")
        assert data["policy_line"]


def test_leading_indicator_endpoint_smoke():
    res = client.get("/api/v1/analytics/leading-indicator")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in (
        "COMPLETED",
        "INSUFFICIENT_PROTOTYPE_HISTORY",
        "NO_BENCHMARK",
        "INSUFFICIENT_ALIGNMENT",
    )
    if data["status"] == "COMPLETED":
        assert "best_lag_weeks" in data
        assert 0 <= data["best_lag_weeks"] <= 4


def test_explainable_alerts_endpoint_smoke():
    res = client.get("/api/v1/analytics/alerts")
    assert res.status_code == 200
    data = res.json()
    assert "total_alerts" in data
    assert isinstance(data["alerts"], list)
    for alert in data["alerts"]:
        assert "explanation" in alert
        assert "plain_text" in alert["explanation"]


def test_concentration_endpoint_smoke():
    res = client.get("/api/v1/analytics/concentration")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("COMPLETED",)
    assert isinstance(data["routes"], list)
    assert "high_concentration_routes" in data


def test_intraday_volatility_endpoint_smoke():
    res = client.get("/api/v1/analytics/intraday-volatility")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("COMPLETED", "NO_DATA")
    assert isinstance(data["routes"], list)


def test_availability_adjusted_endpoint_smoke():
    res = client.get("/api/v1/analytics/availability-adjusted")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("COMPLETED", "NO_DATA")
    assert "network_headline_fare" in data or "routes" in data


def test_udan_monitor_endpoint_smoke():
    res = client.get("/api/v1/analytics/udan")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("COMPLETED", "NO_UDAN_ROUTES")
    assert isinstance(data["routes"], list)
