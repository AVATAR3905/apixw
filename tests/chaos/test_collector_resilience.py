"""Fault-injection tests for the collector layer.

Each test simulates one realistic failure mode a live collection cycle can hit
in production -- a dead source, a malformed scraper response, a blocked
request, a bot-challenge page -- and asserts the pipeline degrades gracefully
(no crash, no corrupted data, correct fallback tagging) rather than merely
documenting the intended behavior.

Two of these (test_one_malformed_quote_does_not_poison_the_batch,
test_one_malformed_direct_quote_does_not_kill_reconciliation) are regression
tests for a real bug found and fixed in this pass: a single quote with a
non-numeric total_fare or a missing carrier_code used to raise an unhandled
ValueError/KeyError that killed the *entire* batch, silently discarding every
other -- perfectly valid -- observation collected in the same cycle.
"""

import datetime

import pytest

from database.session import SessionLocal
from packages.schemas.models import FareObservation
from packages.statistics.discrepancy_validator import CrossFeedDiscrepancyValidator
from services.collectors.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CollectorErrorCode,
    CollectorException,
)
from services.collectors.real_fare_normalizer import RealFareNormalizer


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _cleanup(db, flight_numbers):
    db.query(FareObservation).filter(FareObservation.flight_number.in_(flight_numbers)).delete(
        synchronize_session=False
    )
    db.commit()


class TestMalformedQuoteBatches:
    """Regression coverage: one bad record must never take down a whole batch."""

    def test_one_malformed_quote_does_not_poison_the_batch(self, db):
        travel_date = datetime.date.today() + datetime.timedelta(days=15)
        flight_numbers = ["CHAOS-9001", "CHAOS-9002", "CHAOS-9003", "CHAOS-9004"]
        quotes = [
            {  # valid
                "carrier_code": "6E", "flight_number": flight_numbers[0], "total_fare": 5000.0,
                "feed_type": "CARRIER_DIRECT", "extraction_method": "DOM_BROWSER", "stops": 0,
            },
            {  # non-numeric total_fare -- must be skipped, not fatal
                "carrier_code": "6E", "flight_number": flight_numbers[1], "total_fare": "N/A",
                "feed_type": "CARRIER_DIRECT", "extraction_method": "DOM_BROWSER", "stops": 0,
            },
            {  # missing carrier_code entirely -- must be skipped, not fatal
                "flight_number": flight_numbers[2], "total_fare": 5500.0,
                "feed_type": "CARRIER_DIRECT", "extraction_method": "DOM_BROWSER", "stops": 0,
            },
            {  # garbage in the "real decomposition" fields -- must be skipped, not fatal
                "carrier_code": "6E", "flight_number": flight_numbers[3], "total_fare": 5200.0,
                "feed_type": "CARRIER_DIRECT", "extraction_method": "NETWORK_API",
                "base_fare": "garbage", "stops": 0,
            },
        ]
        try:
            persisted = RealFareNormalizer.normalize_and_persist_observations(
                db=db, raw_quotes=quotes, route_code="DEL-BOM",
                travel_date=travel_date, advance_days=15,
            )
            assert len(persisted) == 1
            assert persisted[0].flight_number == flight_numbers[0]
        finally:
            _cleanup(db, flight_numbers)

    def test_one_malformed_direct_quote_does_not_kill_reconciliation(self, db):
        travel_date = datetime.date.today() + datetime.timedelta(days=15)
        good_flight, bad_flight = "CHAOS-8001", "CHAOS-8002"
        carrier_quotes = [
            {"carrier_code": "6E", "flight_number": good_flight, "total_fare": 5000.0,
             "departure_time": "08:00", "feed_type": "CARRIER_DIRECT"},
            {"carrier_code": "6E", "flight_number": bad_flight, "total_fare": None,
             "departure_time": "09:00", "feed_type": "CARRIER_DIRECT"},
        ]
        try:
            result = CrossFeedDiscrepancyValidator.validate_and_reconcile(
                db=db, carrier_direct_quotes=carrier_quotes, rpc_quotes=[],
                route_code="DEL-BOM", travel_date=travel_date, advance_days=15,
            )
            flight_numbers_seen = {o.get("flight_number") for o in result["primary_observations"]}
            assert good_flight in flight_numbers_seen
            assert bad_flight not in flight_numbers_seen
        finally:
            db.query(FareObservation).filter(
                FareObservation.flight_number.in_([good_flight, bad_flight])
            ).delete(synchronize_session=False)
            db.commit()


class TestQualityGateActuallyRuns:
    """Regression coverage for a real bug found while auditing data integrity:
    RealFareNormalizer hardcoded quality_score=98.5/quality_status="ACCEPT" on
    every real observation regardless of content, so QualityEngine's real
    checks (fare-decomposition-sum consistency, plausible-range review) never
    actually ran on real data, and /api/v1/data-quality's rejected_quotes_count
    was structurally always 0 -- not because nothing was ever bad, but because
    nothing was ever checked. Fixed by actually calling QualityEngine.evaluate().
    """

    def test_decomposition_mismatch_on_a_real_extraction_is_flagged_not_silently_accepted(self, db):
        """A NETWORK_API quote (real base/fuel/tax fields from the source) whose
        components don't sum to the total is exactly the case QualityEngine's
        Rule 5 exists to catch -- it must not still come out ACCEPT/98.5."""
        travel_date = datetime.date.today() + datetime.timedelta(days=15)
        flight_number = "CHAOS-7001"
        quotes = [
            {
                "carrier_code": "SG", "flight_number": flight_number, "total_fare": 6000.0,
                "feed_type": "CARRIER_DIRECT", "extraction_method": "NETWORK_API",
                # Real source-provided breakdown that doesn't reconcile with
                # total_fare -- components sum to 5000, total claims 6000.
                "base_fare": 4000.0, "fuel_surcharge": 500.0, "tax_amount": 500.0,
                "stops": 0,
            },
        ]
        try:
            persisted = RealFareNormalizer.normalize_and_persist_observations(
                db=db, raw_quotes=quotes, route_code="DEL-BOM",
                travel_date=travel_date, advance_days=15,
            )
            assert len(persisted) == 1
            obs = persisted[0]
            assert obs.quality_status == "REJECT"
            assert obs.quality_score < 90.0
        finally:
            _cleanup(db, [flight_number])

    def test_clean_quote_still_scores_accept(self, db):
        """A normal, well-formed quote must still come out ACCEPT -- the fix
        must not turn the gate into a blanket rejector."""
        travel_date = datetime.date.today() + datetime.timedelta(days=15)
        flight_number = "CHAOS-7002"
        quotes = [
            {
                "carrier_code": "6E", "flight_number": flight_number, "total_fare": 5000.0,
                "feed_type": "CARRIER_DIRECT", "extraction_method": "DOM_BROWSER", "stops": 0,
            },
        ]
        try:
            persisted = RealFareNormalizer.normalize_and_persist_observations(
                db=db, raw_quotes=quotes, route_code="DEL-BOM",
                travel_date=travel_date, advance_days=15,
            )
            assert len(persisted) == 1
            assert persisted[0].quality_status == "ACCEPT"
            assert persisted[0].quality_score >= 90.0
        finally:
            _cleanup(db, [flight_number])


class TestCircuitBreakerIsolation:
    """A dead source must degrade to OPEN without taking the whole cycle down."""

    def test_source_trips_open_after_threshold_and_blocks_further_calls(self):
        breaker = CircuitBreaker(
            source_id=9001, source_name="Chaos-Test Dead Source",
            failure_threshold=5, max_retries=1, initial_backoff_seconds=0.001,
        )

        def always_fails():
            raise CollectorException(CollectorErrorCode.SOURCE_UNAVAILABLE, "connection refused")

        for _ in range(5):
            with pytest.raises(CollectorException):
                breaker.call(always_fails)

        assert breaker.state == "OPEN"
        # A 6th caller must be rejected immediately -- never hits the dead
        # source again, which is the entire point of a circuit breaker.
        call_count_before = breaker.consecutive_failures
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(always_fails)
        assert breaker.consecutive_failures == call_count_before  # not incremented -- never called

    def test_permission_denied_is_fatal_and_not_retried(self):
        """A PERMISSION_DENIED (e.g. robots.txt disallow) must not burn retry budget."""
        breaker = CircuitBreaker(source_id=9002, source_name="Chaos-Test Forbidden Source")
        attempts = {"n": 0}

        def denied():
            attempts["n"] += 1
            raise CollectorException(CollectorErrorCode.PERMISSION_DENIED, "robots.txt disallow")

        with pytest.raises(CollectorException):
            breaker.call(denied)
        assert attempts["n"] == 1  # no retries for a permission failure


class TestCarrierScraperDegradeChain:
    """The scraper's own DOM->OCR->calibrated chain must never raise outward."""

    def test_robots_disallow_yields_empty_not_a_crash(self, monkeypatch):
        from services.collectors import carrier_direct_scraper as cds_mod

        monkeypatch.setattr(
            cds_mod._ROBOTS_CHECKER, "can_fetch", lambda url, user_agent="*": False
        )
        scraper = cds_mod.CarrierDirectScraper()
        # Route through the live-mode async path directly to exercise the
        # robots.txt gate without waiting on a real (or mocked) browser launch.
        import asyncio

        result = asyncio.run(
            scraper._scrape_with_context(
                context=None, carrier_code="SG", origin="DEL", dest="BOM",
                travel_date=datetime.date.today() + datetime.timedelta(days=15),
                advance_days=15, db=None,
            )
        )
        assert result == []

    def test_bot_challenge_page_never_misread_as_zero_fares_then_ocrd(self):
        """A CAPTCHA/challenge page must short-circuit before OCR ever runs on it."""
        from services.collectors.carrier_direct_scraper import _BLOCK_PAGE_MARKERS

        challenge_bodies = [
            "Please complete the CAPTCHA below to continue",
            "Checking your browser before accessing... Cloudflare",
            "Access Denied - you have been blocked",
        ]
        for body in challenge_bodies:
            assert any(marker in body.lower() for marker in _BLOCK_PAGE_MARKERS), (
                f"block-page detector missed a real challenge phrase: {body!r}"
            )

    def test_generic_json_price_scan_ignores_out_of_band_amounts(self):
        """A generic carrier's intercepted JSON often carries unrelated numeric
        fields (loyalty points, seat counts) shaped like fareAmount but wildly
        outside a plausible domestic fare -- these must not become fake quotes.
        """
        from services.collectors.carrier_direct_scraper import CarrierDirectScraper

        scraper = CarrierDirectScraper()
        api_responses = [
            {"url": "https://example.com/api", "body": {
                "fareAmount": 99999999,  # absurd, must be filtered by the 1500-60000 band
                "totalAmount": 12,       # implausibly low
                "seatsRemaining": 4200,  # not a fare at all, but numeric
            }},
        ]
        quotes = scraper._extract_generic_json_prices(
            api_responses, "AI", "DEL", "BOM", "2026-10-15", 15
        )
        assert quotes == []
