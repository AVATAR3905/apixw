"""Unit and integration tests for Researcher Exports, API routers, and Rate Limiting (Phase 9)."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_export_daily_index_csv():
    """Tests CSV export endpoint for daily index series."""
    res = client.get("/api/v1/export/daily-index.csv?series=BASE_FARE&horizon=15")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "attachment" in res.headers["content-disposition"]
    assert "date,index_series,index_type" in res.text
    assert ("HEADLINE_T15" in res.text) or ("HEADLINE_T14" in res.text)


def test_export_daily_index_json():
    """Tests JSON export endpoint for daily index series."""
    res = client.get("/api/v1/export/daily-index.json?series=BASE_FARE&horizon=15")
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    data = res.json()
    assert isinstance(data, list)
    if len(data) > 0:
        assert "index_value" in data[0]
        assert "lead_time_days" in data[0]


def test_export_basket_weights_csv():
    """Tests CSV export of DGCA route basket weights."""
    res = client.get("/api/v1/export/basket-weights.csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "route_code,origin_airport,destination_airport" in res.text
    assert "DEL-BOM" in res.text


def test_export_route_observations_csv():
    """Tests CSV export of raw observations for a corridor."""
    res = client.get("/api/v1/export/route-observations.csv?route_code=DEL-BOM&limit=10")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "flight_number,cabin_class,fare_family" in res.text


def test_daily_filtered_indices_endpoint():
    """Tests date filtering on GET /api/v1/index/daily."""
    res = client.get(
        "/api/v1/index/daily?from=2026-08-01&to=2026-08-10&series=BASE_FARE&horizon=15"
    )
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    for row in data:
        assert "2026-08-01" <= row["date"] <= "2026-08-10"


def test_monthly_aggregated_indices_endpoint():
    """Tests monthly aggregated series endpoint."""
    res = client.get("/api/v1/index/monthly?series=BASE_FARE")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)


def test_weights_endpoint():
    """Tests GET /api/v1/weights."""
    res = client.get("/api/v1/weights")
    assert res.status_code == 200
    weights = res.json()
    assert len(weights) >= 10
    del_bom = next(w for w in weights if w["route_code"] == "DEL-BOM")
    assert del_bom["normalized_weight"] > 0.15


def test_rate_limiting_headers():
    """Tests that rate limiting headers are injected on API requests."""
    res = client.get("/api/v1/index")
    assert res.status_code == 200
    assert "X-RateLimit-Limit" in res.headers
    assert "X-RateLimit-Remaining" in res.headers
