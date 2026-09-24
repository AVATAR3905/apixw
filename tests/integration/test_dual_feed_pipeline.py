"""Integration Tests for Dual-Feed Pipeline (Carrier Direct Priority & RPC Fallback)."""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from database.session import SessionLocal
from packages.schemas.models import DiscrepancyAudit, FareObservation
from services.collectors.dual_feed_runner import run_dual_feed_collection


@pytest.fixture
def test_client():
    return TestClient(app)


def test_dual_feed_execution_and_storage(carrier_direct_live_fake):
    """Runs a real-world collection cycle and verifies that observations have is_synthetic=False."""
    result = run_dual_feed_collection(route_code="DEL-BOM", advance_days=7)

    assert result["total_flights_evaluated"] > 0
    assert result["route_code"] == "DEL-BOM"

    db = SessionLocal()
    try:
        # Verify persistence of real-world observations
        real_quotes = (
            db.query(FareObservation)
            .filter(
                FareObservation.is_synthetic.is_(False),
                FareObservation.advance_purchase_days == 7,
            )
            .all()
        )
        assert len(real_quotes) > 0

        # Verify carrier direct priority
        carrier_direct_quotes = [q for q in real_quotes if q.feed_type == "CARRIER_DIRECT"]
        assert len(carrier_direct_quotes) > 0

        # Verify Section 62 decomposition fields are populated
        for q in real_quotes:
            assert q.base_fare > 0
            assert q.tax_amount >= 0
            assert q.development_fee >= 0
            assert q.total_fare >= 1500.0
            assert q.quality_status == "ACCEPT"

        # Verify audits exist
        audits = db.query(DiscrepancyAudit).all()
        assert len(audits) > 0

    finally:
        db.close()


def test_cross_feed_api_endpoints(test_client):
    """Verifies that /api/v1/validation/cross-feed and /api/v1/data-quality report real-world metrics."""
    res = test_client.get("/api/v1/validation/cross-feed?route_code=DEL-BOM")
    assert res.status_code == 200
    data = res.json()
    assert "total_audits" in data
    assert "carrier_direct_count" in data
    assert "rpc_fallback_count" in data
    assert "audits" in data

    dq_res = test_client.get("/api/v1/data-quality")
    assert dq_res.status_code == 200
    dq_data = dq_res.json()
    assert dq_data["real_life_quotes_count"] > 0
    assert "carrier_direct_quotes_count" in dq_data
    assert "rpc_fallback_quotes_count" in dq_data
