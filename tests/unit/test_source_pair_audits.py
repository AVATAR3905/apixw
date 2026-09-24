"""Tests for OTA feed_type tagging and Phase 2 source-pair markup audits."""

import datetime

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from database.session import SessionLocal
from packages.statistics.source_pair_auditor import SourcePairAuditor
from services.collectors.ota.cleartrip_scraper import CleartripScraper
from services.collectors.ota.easemytrip_scraper import EaseMyTripScraper
from services.collectors.ota.ixigo_scraper import IxigoScraper
from services.collectors.ota.makemytrip_scraper import MakeMyTripScraper
from services.collectors.ota.skyscanner_scraper import SkyscannerScraper
from services.collectors.ota.yatra_scraper import YatraScraper


@pytest.fixture
def client():
    return TestClient(app)


def test_ota_scrapers_emit_feed_type():
    """All 6 OTA scrapers must tag every quote with feed_type == 'OTA_AGGREGATOR'."""
    scrapers = [
        MakeMyTripScraper(),
        IxigoScraper(),
        EaseMyTripScraper(),
        YatraScraper(),
        CleartripScraper(),
        SkyscannerScraper(),
    ]
    travel = datetime.date(2026, 9, 20)
    db = SessionLocal()
    try:
        for s in scrapers:
            quotes = s.scrape_corridor("DEL", "BOM", travel, 15, db=db)
            assert len(quotes) > 0, f"{s.source_name} returned no quotes"
            for q in quotes:
                assert q["feed_type"] == "OTA_AGGREGATOR", (
                    f"{s.source_name} quote feed_type is {q.get('feed_type')!r}"
                )
    finally:
        db.close()


def test_source_pair_auditor_unit():
    """SourcePairAuditor: mock quotes across carrier-direct + 2 OTAs produce correct audits."""
    mock_quotes = [
        {
            "source_id": 5,
            "source_name": "Carrier Direct (IndiGo)",
            "source_domain": "6e.airline.direct",
            "carrier_code": "6E",
            "flight_number": "6E-205",
            "origin_airport": "DEL",
            "destination_airport": "BOM",
            "travel_date": "2026-09-20",
            "departure_time": "06:00",
            "arrival_time": "08:15",
            "total_fare": 3500.0,
            "feed_type": "CARRIER_DIRECT",
            "convenience_fee": 0.0,
        },
        {
            "source_id": 7,
            "source_name": "MakeMyTrip India",
            "source_domain": "makemytrip.com",
            "carrier_code": "6E",
            "flight_number": "6E-205",
            "origin_airport": "DEL",
            "destination_airport": "BOM",
            "travel_date": "2026-09-20",
            "departure_time": "06:00",
            "arrival_time": "08:15",
            "total_fare": 3920.0,
            "feed_type": "OTA_AGGREGATOR",
            "convenience_fee": 420.0,
        },
        {
            "source_id": 9,
            "source_name": "EaseMyTrip",
            "source_domain": "easemytrip.com",
            "carrier_code": "6E",
            "flight_number": "6E-205",
            "origin_airport": "DEL",
            "destination_airport": "BOM",
            "travel_date": "2026-09-20",
            "departure_time": "06:00",
            "arrival_time": "08:15",
            "total_fare": 3500.0,
            "feed_type": "OTA_AGGREGATOR",
            "convenience_fee": 0.0,
        },
    ]

    db = SessionLocal()
    try:
        from packages.schemas.models import DiscrepancyAudit

        scope = (
            DiscrepancyAudit.audit_type == "OTA_SOURCE_PAIR",
            DiscrepancyAudit.travel_date == datetime.date(2026, 9, 20),
            DiscrepancyAudit.source_a_name == "Carrier Direct (IndiGo)",
        )
        prior = db.query(DiscrepancyAudit).filter(*scope).count()

        result = SourcePairAuditor.audit_source_pairs(
            db=db,
            quotes=mock_quotes,
            route_code="DEL-BOM",
            travel_date=datetime.date(2026, 9, 20),
            advance_days=15,
            persist=True,
        )
        assert result["pairs_evaluated"] == 2
        assert result["markup_count"] == 1  # MakeMyTrip
        assert result["parity_count"] == 1  # EaseMyTrip = Carrier Direct
        assert result["discount_count"] == 0

        # Exactly 2 new rows should have been persisted
        audits = db.query(DiscrepancyAudit).filter(*scope).all()
        assert len(audits) == prior + 2
        mmt_audit = [a for a in audits if a.source_b_name == "MakeMyTrip India"][-1]
        assert mmt_audit.price_a == 3500.0
        assert mmt_audit.price_b == 3920.0
        assert mmt_audit.markup_amount == 420.0
        assert mmt_audit.validation_status == "AGGREGATOR_MARKUP"
    finally:
        db.close()


def test_source_pair_api_returns_audits(client, carrier_baseline):
    """GET /api/v1/validation/source-pair returns persisted OTA_SOURCE_PAIR audits."""
    # Run the auditor to populate the DB
    db = SessionLocal()
    try:
        from services.collectors.ota.multi_source_orchestrator import MultiSourceFlightOrchestrator

        collection = MultiSourceFlightOrchestrator().collect_corridor_all_sources(
            route_code="DEL-BOM", advance_days=15, db=db
        )
        travel_date = datetime.date.fromisoformat(collection["travel_date"])
        SourcePairAuditor.audit_source_pairs(
            db=db,
            quotes=collection["all_quotes"],
            route_code="DEL-BOM",
            travel_date=travel_date,
            advance_days=15,
            persist=True,
        )
    finally:
        db.close()

    res = client.get("/api/v1/validation/source-pair")
    assert res.status_code == 200
    data = res.json()
    assert "total_audits" in data
    assert "audits" in data
    assert data["total_audits"] > 0
    row = data["audits"][0]
    assert "source_a" in row
    assert "source_b" in row
    assert "markup_amount" in row
    assert "price_a" in row
    assert "price_b" in row
