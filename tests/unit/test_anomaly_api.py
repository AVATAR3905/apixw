"""Smoke tests for Phase 4 anomaly detection endpoints and index confidence score."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_index_returns_confidence_score():
    """GET /api/v1/index must now include confidence_score and confidence_band."""
    res = client.get("/api/v1/index")
    assert res.status_code == 200
    data = res.json()
    assert "confidence_score" in data
    assert "confidence_band" in data
    assert "outlier_count" in data
    assert data["confidence_band"] in ("HIGH", "MEDIUM", "LOW")
    assert 0.0 <= data["confidence_score"] <= 100.0


def test_anomaly_detection_run_returns_completed():
    """POST /analytics/run-anomaly-detection returns COMPLETED or INSUFFICIENT_DATA."""
    res = client.post("/api/v1/analytics/run-anomaly-detection?series=BASE_FARE&window_days=28")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("COMPLETED", "INSUFFICIENT_DATA")
    assert "severity_counts" in data or "points_scanned" in data


def test_anomaly_events_endpoint_smoke():
    """GET /analytics/anomalies must return a valid envelope (may be empty)."""
    res = client.get("/api/v1/analytics/anomalies")
    assert res.status_code == 200
    data = res.json()
    assert "total_events" in data
    assert "severity_counts" in data
    assert "open_count" in data
    assert isinstance(data["events"], list)
