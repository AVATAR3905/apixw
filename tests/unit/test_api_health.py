"""Unit test for FastAPI health endpoint."""

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "India Airfare Price Observatory" in data["service"]
    assert data["anchor_lead_time"] == "T+15"
    assert data["active_methodology_version"] == "APIX-2.0"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
