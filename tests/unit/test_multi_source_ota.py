"""
Unit and Integration Tests for Multi-Source OTA & Direct Carrier Pipeline.
Tests:
- 6 OTA Scrapers (MakeMyTrip, Ixigo, EaseMyTrip, Yatra, Cleartrip, Skyscanner)
- 4 Flight Carriers (IndiGo, Air India, SpiceJet, Akasa Air)
- Canonical Entity Resolution (FlightEntityMatcher)
- MoSPI CPI Harmonized Pricing Engine (CanonicalPricer)
- FastAPI /api/v1/ota Endpoints
"""

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from database.session import SessionLocal
from packages.statistics.canonical_pricer import CanonicalPricer
from packages.statistics.flight_matcher import FlightEntityMatcher
from services.collectors.ota.cleartrip_scraper import CleartripScraper
from services.collectors.ota.easemytrip_scraper import EaseMyTripScraper
from services.collectors.ota.ixigo_scraper import IxigoScraper
from services.collectors.ota.makemytrip_scraper import MakeMyTripScraper
from services.collectors.ota.multi_source_orchestrator import MultiSourceFlightOrchestrator
from services.collectors.ota.skyscanner_scraper import SkyscannerScraper
from services.collectors.ota.yatra_scraper import YatraScraper


@pytest.fixture
def client():
    return TestClient(app)


def test_ota_scrapers_initialization():
    """Verify all 6 OTAs instantiate with valid domains, fees, and circuit breakers."""
    scrapers = [
        MakeMyTripScraper(),
        IxigoScraper(),
        EaseMyTripScraper(),
        YatraScraper(),
        CleartripScraper(),
        SkyscannerScraper(),
    ]

    expected_fees = {
        "makemytrip.com": 420.0,
        "ixigo.com": 360.0,
        "easemytrip.com": 0.0,
        "yatra.com": 399.0,
        "cleartrip.com": 349.0,
        "skyscanner.co.in": 0.0,
    }

    for s in scrapers:
        assert s.domain in expected_fees
        assert s.standard_convenience_fee == expected_fees[s.domain]
        assert s.circuit_breaker.state == "CLOSED"


def test_flight_matcher_normalization():
    """Verify alphanumeric IATA normalization (especially 6E starting with a digit)."""
    assert FlightEntityMatcher.normalize_flight_number("6E-205") == "6E-205"
    assert FlightEntityMatcher.normalize_flight_number("6E 532") == "6E-532"
    assert FlightEntityMatcher.normalize_flight_number("AI-806") == "AI-806"
    assert FlightEntityMatcher.normalize_flight_number("QP-1102") == "QP-1102"
    assert FlightEntityMatcher.normalize_flight_number("SG-8169") == "SG-8169"
    assert FlightEntityMatcher.normalize_flight_number("205", "6E") == "6E-205"


def test_flight_matcher_clustering():
    """Verify multi-platform quotes for identical flights cluster together."""
    mock_quotes = [
        {
            "carrier_code": "6E",
            "flight_number": "6E-205",
            "origin_airport": "DEL",
            "destination_airport": "BOM",
            "travel_date": "2026-09-18",
            "departure_time": "06:00",
            "arrival_time": "08:15",
            "source_name": "Carrier Direct (IndiGo)",
            "source_domain": "6e.airline.direct",
            "total_fare": 3540.0,
            "convenience_fee": 0.0,
        },
        {
            "carrier_code": "6E",
            "flight_number": "6E 205",
            "origin_airport": "DEL",
            "destination_airport": "BOM",
            "travel_date": "2026-09-18",
            "departure_time": "06:05",
            "arrival_time": "08:20",
            "source_name": "MakeMyTrip India",
            "source_domain": "makemytrip.com",
            "total_fare": 3960.0,
            "convenience_fee": 420.0,
        },
        {
            "carrier_code": "6E",
            "flight_number": "205",
            "origin_airport": "DEL",
            "destination_airport": "BOM",
            "travel_date": "2026-09-18",
            "departure_time": "06:00",
            "arrival_time": "08:15",
            "source_name": "EaseMyTrip",
            "source_domain": "easemytrip.com",
            "total_fare": 3540.0,
            "convenience_fee": 0.0,
        },
    ]

    clusters = FlightEntityMatcher.cluster_common_flights(mock_quotes)
    assert len(clusters) == 1
    cluster = list(clusters.values())[0]
    assert cluster["carrier_code"] == "6E"
    assert cluster["flight_number"] == "6E-205"
    assert len(cluster["all_quotes"]) == 3


def test_canonical_pricer_median_and_dispersion():
    """Verify Harmonized Platform Median calculation across Direct + OTAs."""
    mock_quotes = [
        {
            "source_name": "Carrier Direct (IndiGo)",
            "source_domain": "6e.airline.direct",
            "base_fare": 3500.0,
            "total_fare": 3500.0,
            "convenience_fee": 0.0,
            "promotional_discount": 0.0,
        },
        {
            "source_name": "EaseMyTrip",
            "source_domain": "easemytrip.com",
            "base_fare": 3500.0,
            "total_fare": 3500.0,
            "convenience_fee": 0.0,
            "promotional_discount": 0.0,
        },
        {
            "source_name": "Cleartrip",
            "source_domain": "cleartrip.com",
            "base_fare": 3500.0,
            "total_fare": 3849.0,
            "convenience_fee": 349.0,
            "promotional_discount": 0.0,
        },
        {
            "source_name": "Ixigo",
            "source_domain": "ixigo.com",
            "base_fare": 3500.0,
            "total_fare": 3860.0,
            "convenience_fee": 360.0,
            "promotional_discount": 0.0,
        },
        {
            "source_name": "MakeMyTrip",
            "source_domain": "makemytrip.com",
            "base_fare": 3500.0,
            "total_fare": 3920.0,
            "convenience_fee": 420.0,
            "promotional_discount": 0.0,
        },
    ]
    cluster = {
        "carrier_code": "6E",
        "flight_number": "6E-205",
        "carrier_name": "IndiGo",
        "origin_airport": "DEL",
        "destination_airport": "BOM",
        "travel_date": "2026-09-18",
        "departure_time": "06:00",
        "arrival_time": "08:15",
        "all_quotes": mock_quotes,
    }

    priced = CanonicalPricer.price_common_flight(cluster)
    assert priced is not None
    # Median of [3500, 3500, 3849, 3860, 3920] = 3849.0
    assert priced["canonical_median_fare"] == 3849.0
    assert priced["min_walkaway_fare"] == 3500.0
    assert priced["max_observed_fare"] == 3920.0
    assert priced["spread_inr"] == 420.0
    assert priced["carrier_direct_fare"] == 3500.0
    assert priced["sources_count"] == 5


def test_multi_source_orchestrator_execution(carrier_baseline):
    """Verify orchestrator harvests quotes across all 4 carriers and 6 OTAs."""
    db = SessionLocal()
    try:
        orch = MultiSourceFlightOrchestrator()
        res = orch.collect_corridor_all_sources(route_code="DEL-BOM", advance_days=15, db=db)

        assert res["route_code"] == "DEL-BOM"
        assert res["total_quotes_collected"] > 0
        assert res["carrier_quotes_count"] > 0
        assert len(res["ota_quotes_by_source"]) == 6

        # Verify cluster generation
        clusters = FlightEntityMatcher.cluster_common_flights(res["all_quotes"])
        assert len(clusters) > 0

        priced = [CanonicalPricer.price_common_flight(c) for c in clusters.values()]
        assert len(priced) > 0
    finally:
        db.close()


def test_api_endpoints_ota(client, carrier_baseline):
    """Verify all /api/v1/ota endpoints respond successfully with valid schemas."""
    # 1. Common flights endpoint
    res = client.get("/api/v1/ota/common-flights?route_code=DEL-BOM&horizon=15")
    assert res.status_code == 200
    data = res.json()
    assert data["route_code"] == "DEL-BOM"
    assert data["horizon_days"] == 15
    assert len(data["common_flights"]) > 0
    cf = data["common_flights"][0]
    assert "canonical_median_fare" in cf
    assert "platform_matrix" in cf

    # 2. Dispersion ranking endpoint
    res_rank = client.get("/api/v1/ota/dispersion-ranking?route_code=DEL-BOM&horizon=15")
    assert res_rank.status_code == 200
    rank_data = res_rank.json()
    assert rank_data["total_flights_analyzed"] > 0
    assert len(rank_data["platform_rankings"]) > 0

    # 3. Sources status endpoint
    res_status = client.get("/api/v1/ota/sources-status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["active_sources_count"] == 7
    assert status_data["carrier_direct_count"] == 4
    assert status_data["ota_count"] == 6
