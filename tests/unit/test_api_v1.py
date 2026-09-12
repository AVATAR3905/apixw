"""Unit tests verifying REST API v1 endpoints."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_api_v1_index_endpoint():
    res = client.get("/api/v1/index")
    assert res.status_code == 200
    data = res.json()
    assert "index_value" in data
    assert data["index_series"] == "BASE_FARE"
    assert data["lead_time_days"] in (14, 15)


def test_api_v1_index_timeseries():
    res = client.get("/api/v1/index/timeseries")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_api_v1_routes():
    res = client.get("/api/v1/routes")
    assert res.status_code == 200
    routes = res.json()
    assert len(routes) == 10
    del_bom = next(r for r in routes if r["route_code"] == "DEL-BOM")
    assert del_bom["corridor_type"] == "METRO_TRUNK"


def test_api_v1_route_detail():
    res = client.get("/api/v1/routes/DEL-BOM")
    assert res.status_code == 200
    detail = res.json()
    assert detail["route_code"] == "DEL-BOM"
    assert "fare_decomposition" in detail


def test_api_v1_lead_time():
    res = client.get("/api/v1/lead-time?route_code=DEL-BOM")
    assert res.status_code == 200
    data = res.json()
    assert data["surge_multiplier"] >= 2.0
    assert len(data["lead_time_curve"]) == 5


def test_api_v1_validation():
    res = client.get("/api/v1/validation")
    assert res.status_code == 200
    data = res.json()
    assert data["metrics"]["directional_accuracy_pct"] >= 80.0
    assert "methodology_disclosure" in data


def test_api_v1_quality_and_sources():
    q_res = client.get("/api/v1/data-quality")
    assert q_res.status_code == 200
    assert q_res.json()["quote_capture_rate_pct"] >= 90.0

    s_res = client.get("/api/v1/source-health")
    assert s_res.status_code == 200
    assert len(s_res.json()) >= 1


def test_api_v1_fuel_and_methodology():
    f_res = client.get("/api/v1/fuel-context")
    assert f_res.status_code == 200
    assert "operating_cost_share_pct" in f_res.json()

    m_res = client.get("/api/v1/methodology")
    assert m_res.status_code == 200
    assert len(m_res.json()["basket_weights"]) == 10
