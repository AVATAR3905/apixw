"""Hermetic unit tests for the Amadeus Self-Service API licensed GDS adapter.

These tests never touch the network: the flight-offers payload parser is
exercised against a realistic fixture, and the no-credentials path is verified
via the base class's calibrated fallback (db-less).
"""

import datetime

from packages.shared.config import settings
from services.collectors.ota.amadeus_scraper import (
    AmadeusCredentialsMissing,
    AmadeusScraper,
    _parse_iso8601_duration,
)


def _flight_offers_payload():
    """Realistic `/v2/shopping/flight-offers` body for DEL->MAA on 2026-10-07."""
    return {
        "data": [
            {
                "id": "1",
                "numberOfBookableSeats": 9,
                "itineraries": [
                    {
                        "duration": "PT2H05M",
                        "segments": [
                            {
                                "departure": {
                                    "iataCode": "DEL",
                                    "terminal": "3",
                                    "at": "2026-10-07T06:00:00",
                                },
                                "arrival": {
                                    "iataCode": "MAA",
                                    "terminal": "1",
                                    "at": "2026-10-07T08:05:00",
                                },
                                "carrierCode": "AI",
                                "number": "806",
                                "duration": "PT2H05M",
                                "numberOfStops": 0,
                            }
                        ],
                    }
                ],
                "price": {
                    "currency": "INR",
                    "total": "5450.00",
                    "base": "4900.00",
                    "grandTotal": "5450.00",
                },
            },
            {
                # Sold-out offer -> 0 bookable seats must map to inventory SOLD_OUT.
                "id": "2",
                "numberOfBookableSeats": 0,
                "itineraries": [
                    {
                        "duration": "PT2H30M",
                        "segments": [
                            {
                                "departure": {"iataCode": "DEL", "at": "2026-10-07T09:30:00"},
                                "arrival": {"iataCode": "MAA", "at": "2026-10-07T12:00:00"},
                                "carrierCode": "6E",
                                "number": "205",
                                "duration": "PT2H30M",
                                "numberOfStops": 0,
                            }
                        ],
                    }
                ],
                "price": {"currency": "INR", "total": "5200.00", "base": "4700.00", "grandTotal": "5200.00"},
            },
            {
                # Duplicate of offer 2 (same flight identifier + departure) -> dropped.
                "id": "3",
                "numberOfBookableSeats": 5,
                "itineraries": [
                    {
                        "duration": "PT2H30M",
                        "segments": [
                            {
                                "departure": {"iataCode": "DEL", "at": "2026-10-07T09:30:00"},
                                "arrival": {"iataCode": "MAA", "at": "2026-10-07T12:00:00"},
                                "carrierCode": "6E",
                                "number": "205",
                                "duration": "PT2H30M",
                                "numberOfStops": 0,
                            }
                        ],
                    }
                ],
                "price": {"currency": "INR", "total": "5600.00", "base": "5100.00", "grandTotal": "5600.00"},
            },
            {
                # Outside PRD Section-62 fare bounds -> dropped.
                "id": "4",
                "numberOfBookableSeats": 4,
                "itineraries": [
                    {
                        "duration": "PT2H05M",
                        "segments": [
                            {
                                "departure": {"iataCode": "DEL", "at": "2026-10-07T20:00:00"},
                                "arrival": {"iataCode": "MAA", "at": "2026-10-07T22:05:00"},
                                "carrierCode": "AI",
                                "number": "808",
                                "duration": "PT2H05M",
                                "numberOfStops": 0,
                            }
                        ],
                    }
                ],
                "price": {"currency": "INR", "total": "900.00", "base": "700.00", "grandTotal": "900.00"},
            },
        ]
    }


def test_parse_iso8601_duration():
    assert _parse_iso8601_duration("PT2H05M") == 125
    assert _parse_iso8601_duration("PT45M") == 45
    assert _parse_iso8601_duration("PT1H") == 60
    assert _parse_iso8601_duration("") == 0
    assert _parse_iso8601_duration(None) == 0


def test_parse_flight_offers_maps_uniform_schema():
    scraper = AmadeusScraper()
    quotes = scraper.parse_flight_offers(
        _flight_offers_payload(), "DEL", "MAA", datetime.date(2026, 10, 7), 15
    )

    # Offer 3 (dup) and offer 4 (fare out of bounds) are dropped.
    assert len(quotes) == 2

    ai = next(q for q in quotes if q["carrier_code"] == "AI")
    # SIH 26056 uniform schema
    assert ai["provider_id"] == "Amadeus Self-Service API"
    assert ai["flight_identifier"] == "AI-806"
    assert ai["departure_iso"] == "2026-10-07T06:00:00"
    assert ai["arrival_iso"] == "2026-10-07T08:05:00"
    assert ai["duration_minutes"] == 125
    assert ai["stopover_count"] == 0
    assert ai["inventory_status"] == "AVAILABLE"
    assert ai["fare_breakdown"] == {
        "base_fare": 4900.0,
        "taxes_fees": 550.0,
        "total_payable": 5450.0,
    }
    assert ai["total_fare"] == 5450.0
    assert ai["tax_amount"] == 550.0
    # repo-native fields
    assert ai["flight_number"] == "AI-806"
    assert ai["departure_time"] == "06:00"
    assert ai["arrival_time"] == "08:05"
    assert ai["stops"] == 0
    assert ai["is_sold_out"] is False
    # feed_type is stamped by BaseOTAScraper.scrape_corridor from FEED_TYPE
    # (verified end-to-end in test_calibrated_fallback_when_no_credentials).
    assert AmadeusScraper.FEED_TYPE == "PARTNER_API"
    assert ai["extraction_method"] == "NETWORK_API"

    six_e = next(q for q in quotes if q["carrier_code"] == "6E")
    assert six_e["is_sold_out"] is True
    assert six_e["inventory_status"] == "SOLD_OUT"
    assert six_e["duration_minutes"] == 150


def test_missing_credentials_raises():
    scraper = AmadeusScraper()
    try:
        scraper._credentials()
        assert False, "expected AmadeusCredentialsMissing"
    except AmadeusCredentialsMissing:
        pass


def test_calibrated_fallback_when_no_credentials(monkeypatch):
    """Without a key, scrape_corridor must degrade to the tagged fallback."""
    monkeypatch.setattr(settings, "AMADEUS_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AMADEUS_CLIENT_SECRET", "")
    monkeypatch.delenv("AMADEUS_CLIENT_ID", raising=False)
    monkeypatch.delenv("AMADEUS_CLIENT_SECRET", raising=False)

    scraper = AmadeusScraper()
    quotes = scraper.scrape_corridor(
        origin_airport="DEL",
        destination_airport="MAA",
        travel_date=datetime.date(2026, 10, 7),
        advance_days=15,
        db=None,
    )

    assert len(quotes) > 0
    for q in quotes:
        assert q["feed_type"] == "PARTNER_API"
        assert q["extraction_method"] == "CALIBRATED_MODEL"
        assert q["carrier_code"] in ("6E", "AI")
        assert 1500.0 <= q["total_fare"] <= 60000.0
        # fallback must never carry the REAL extraction tag
        assert q["extraction_method"] != "NETWORK_API"


def test_calibrated_generator_schema(monkeypatch):
    monkeypatch.setattr(settings, "AMADEUS_CLIENT_ID", "")
    monkeypatch.setattr(settings, "AMADEUS_CLIENT_SECRET", "")
    scraper = AmadeusScraper()
    quotes = scraper._generate_calibrated_quotes(
        origin_airport="DEL",
        destination_airport="MAA",
        travel_date=datetime.date(2026, 10, 7),
        advance_days=15,
    )
    assert len(quotes) == 5
    for q in quotes:
        assert q["duration_minutes"] == 150
        assert q["stopover_count"] == 0
        assert q["inventory_status"] == "AVAILABLE"
        assert q["departure_iso"].startswith("2026-10-07T")
