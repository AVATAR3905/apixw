"""Unit and API tests for MarketBriefingService and /analytics/market-briefing endpoint."""

from fastapi.testclient import TestClient

from apps.api.main import app
from database.session import SessionLocal
from packages.statistics.market_briefing import MarketBriefingService

client = TestClient(app)


def test_market_briefing_service():
    """Verifies that MarketBriefingService generates dynamic, data-driven synthesis."""
    db = SessionLocal()
    try:
        data = MarketBriefingService.get_market_briefing(db, horizon_days=15)

        # 1. Headline
        assert "headline" in data
        assert data["headline"]["index_value"] > 0
        assert data["headline"]["anchor_horizon"] == "T+15"

        # 2. Carrier Power
        assert "carrier_power" in data
        assert data["carrier_power"]["inflation_leader"] in (
            "Air India",
            "IndiGo",
            "SpiceJet",
            "Akasa Air",
        )
        assert data["carrier_power"]["value_leader"] in (
            "Air India",
            "IndiGo",
            "SpiceJet",
            "Akasa Air",
        )
        assert data["carrier_power"]["value_leader_min_fare"] > 1000.0
        assert data["carrier_power"]["carrier_spread_pts"] >= 0.0

        # 3. Volatility
        assert "volatility" in data
        assert data["volatility"]["average_network_spread_pct"] > 0.0
        assert data["volatility"]["monitored_corridors_count"] == 10
        assert len(data["volatility"]["top_surge_corridors"]) > 0

        # 4. Lead-Time Elasticity
        assert "lead_time" in data
        assert data["lead_time"]["surge_multiplier"] >= 1.0
        assert data["lead_time"]["t30_savings_pct"] >= 0.0

        # 5. Dynamic Narrative
        assert "narrative" in data
        assert len(data["narrative"]["retail_context"]) > 20
        assert len(data["narrative"]["carrier_summary"]) > 20
        assert len(data["narrative"]["elasticity_summary"]) > 20
        assert len(data["narrative"]["microstructure"]) > 20
        assert len(data["narrative"]["monetary_policy"]) > 20

    finally:
        db.close()


def test_market_briefing_api_endpoint():
    """Verifies that /analytics/market-briefing returns 200 with structured JSON."""
    res = client.get("/api/v1/analytics/market-briefing?horizon=15&series=BASE_FARE")
    assert res.status_code == 200
    payload = res.json()

    assert payload["headline"]["anchor_horizon"] == "T+15"
    assert payload["carrier_power"]["carrier_spread_pts"] >= 0.0
    assert len(payload["volatility"]["top_surge_corridors"]) >= 1
    assert payload["lead_time"]["surge_multiplier"] >= 1.0
    assert "retail_context" in payload["narrative"]
