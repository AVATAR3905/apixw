"""Hermetic unit tests for the Sabre Developer Hub licensed GDS adapter.

These tests never touch the network: the Flight Shop response parser is
exercised against a realistic fixture, the token flow is verified with a
mocked HTTP call, and the no-credentials path is verified via the base
class's calibrated fallback (db-less).
"""

import datetime

from packages.shared.config import settings
from services.collectors.ota.sabre_scraper import (
    SabreCredentialsMissing,
    SabreScraper,
    _parse_iso8601_duration,
)


def _flight_shop_payload():
    """Realistic `/v1/offers/flightShop` body for DEL->MAA on 2026-10-07."""
    return {
        "Offers": [
            {
                "OfferID": "1",
                "Price": {"Amount": 5450.0, "CurrencyCode": "INR", "BaseAmount": 4900.0},
                "Flights": [
                    {
                        "FlightNumber": "AI 806",
                        "Carrier": {"AirlineCode": "AI", "Name": "Air India"},
                        "Departure": {"AirportCode": "DEL", "ScheduledDateTime": "2026-10-07T06:00:00"},
                        "Arrival": {"AirportCode": "MAA", "ScheduledDateTime": "2026-10-07T08:05:00"},
                        "NumberOfStops": 0,
                        "Duration": "PT2H05M",
                    }
                ],
            },
            {
                # Sold-out offer -> SeatsRemaining 0 must map to SOLD_OUT.
                "OfferID": "2",
                "Price": {"Amount": 5200.0, "CurrencyCode": "INR", "BaseAmount": 4700.0},
                "SeatsRemaining": 0,
                "Flights": [
                    {
                        "FlightNumber": "205",
                        "Carrier": {"AirlineCode": "6E", "Name": "IndiGo"},
                        "Departure": {"AirportCode": "DEL", "ScheduledDateTime": "2026-10-07T09:30:00"},
                        "Arrival": {"AirportCode": "MAA", "ScheduledDateTime": "2026-10-07T12:00:00"},
                        "NumberOfStops": 0,
                        "Duration": 150,
                    }
                ],
            },
            {
                # Duplicate of offer 2 (same flight identifier + departure) -> dropped.
                "OfferID": "3",
                "Price": {"Amount": 5600.0, "CurrencyCode": "INR", "BaseAmount": 5100.0},
                "Flights": [
                    {
                        "FlightNumber": "205",
                        "Carrier": {"AirlineCode": "6E", "Name": "IndiGo"},
                        "Departure": {"AirportCode": "DEL", "ScheduledDateTime": "2026-10-07T09:30:00"},
                        "Arrival": {"AirportCode": "MAA", "ScheduledDateTime": "2026-10-07T12:00:00"},
                        "NumberOfStops": 0,
                        "Duration": 150,
                    }
                ],
            },
            {
                # Outside PRD Section-62 fare bounds -> dropped.
                "OfferID": "4",
                "Price": {"Amount": 700.0, "CurrencyCode": "INR", "BaseAmount": 500.0},
                "Flights": [
                    {
                        "FlightNumber": "808",
                        "Carrier": {"AirlineCode": "AI", "Name": "Air India"},
                        "Departure": {"AirportCode": "DEL", "ScheduledDateTime": "2026-10-07T20:00:00"},
                        "Arrival": {"AirportCode": "MAA", "ScheduledDateTime": "2026-10-07T22:05:00"},
                        "NumberOfStops": 0,
                        "Duration": "PT2H05M",
                    }
                ],
            },
        ]
    }


def _flight_groups_payload():
    """Exercises the nested FlightGroups + lower-case field fallback path."""
    return {
        "offers": [
            {
                "price": {"raw": 8422.0, "base": 7500.0},
                "Flights": [
                    {
                        "Flights": [
                            {
                                "flightNumber": "2749",
                                "marketingCarrier": {"displayCode": "IX"},
                                "departure": {"at": "2026-10-07T10:25:00"},
                                "arrival": {"at": "2026-10-07T15:45:00"},
                                "stopCount": 1,
                                "durationInMinutes": 320,
                            }
                        ]
                    }
                ],
            }
        ]
    }


def test_parse_iso8601_duration():
    assert _parse_iso8601_duration("PT2H05M") == 125
    assert _parse_iso8601_duration("PT45M") == 45
    assert _parse_iso8601_duration(150) == 150
    assert _parse_iso8601_duration("") == 0
    assert _parse_iso8601_duration(None) == 0


def test_parse_flight_shop_maps_uniform_schema():
    scraper = SabreScraper()
    quotes = scraper.parse_flight_shop(
        _flight_shop_payload(), "DEL", "MAA", datetime.date(2026, 10, 7), 15
    )

    # Offer 3 (dup) and offer 4 (fare out of bounds) are dropped.
    assert len(quotes) == 2

    ai = next(q for q in quotes if q["carrier_code"] == "AI")
    # SIH 26056 uniform schema
    assert ai["provider_id"] == "Sabre Developer Hub"
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
    assert SabreScraper.FEED_TYPE == "PARTNER_API"
    assert ai["extraction_method"] == "NETWORK_API"

    six_e = next(q for q in quotes if q["carrier_code"] == "6E")
    assert six_e["is_sold_out"] is True
    assert six_e["inventory_status"] == "SOLD_OUT"
    assert six_e["duration_minutes"] == 150  # numeric minute duration


def test_parse_flight_groups_nested_shape():
    scraper = SabreScraper()
    quotes = scraper.parse_flight_shop(
        _flight_groups_payload(), "DEL", "MAA", datetime.date(2026, 10, 7), 15
    )
    assert len(quotes) == 1
    q = quotes[0]
    assert q["flight_identifier"] == "IX-2749"
    assert q["carrier_code"] == "IX"
    assert q["stopover_count"] == 1
    assert q["duration_minutes"] == 320
    assert q["departure_time"] == "10:25"
    assert q["fare_breakdown"]["total_payable"] == 8422.0


def test_missing_credentials_raises(monkeypatch):
    monkeypatch.setattr(settings, "SABRE_USERNAME", "")
    monkeypatch.setattr(settings, "SABRE_PASSWORD", "")
    monkeypatch.delenv("SABRE_USERNAME", raising=False)
    monkeypatch.delenv("SABRE_PASSWORD", raising=False)
    scraper = SabreScraper()
    try:
        scraper._credentials()
        assert False, "expected SabreCredentialsMissing"
    except SabreCredentialsMissing:
        pass


def test_token_fetch_uses_basic_auth_and_caches(monkeypatch):
    """Token exchange must send Basic auth + client_credentials and cache."""
    import base64

    import services.collectors.ota.sabre_scraper as mod

    monkeypatch.setattr(settings, "SABRE_USERNAME", "demo_user")
    monkeypatch.setattr(settings, "SABRE_PASSWORD", "demo_pass")
    monkeypatch.delenv("SABRE_USERNAME", raising=False)
    monkeypatch.delenv("SABRE_PASSWORD", raising=False)
    monkeypatch.setattr(mod, "_token_cache", {"access_token": None, "expires_at": 0.0})

    captured = {}

    class _FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"access_token": "atk-1", "expires_in": 1800}

    def _fake_post(url, data=None, headers=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        return _FakeResp()

    monkeypatch.setattr(mod.requests, "post", _fake_post)

    scraper = SabreScraper()
    assert scraper._get_access_token() == "atk-1"
    # Cached on the second call (no second HTTP hit).
    assert scraper._get_access_token() == "atk-1"
    assert captured["url"].endswith("/v2/auth/token")
    assert captured["data"]["grant_type"] == "client_credentials"
    expected_basic = base64.b64encode(b"demo_user:demo_pass").decode("ascii")
    assert captured["headers"]["Authorization"] == f"Basic {expected_basic}"


def test_calibrated_fallback_when_no_credentials(monkeypatch):
    """Without credentials, scrape_corridor must degrade to the tagged fallback."""
    import services.collectors.ota.sabre_scraper as mod

    monkeypatch.setattr(settings, "SABRE_USERNAME", "")
    monkeypatch.setattr(settings, "SABRE_PASSWORD", "")
    monkeypatch.delenv("SABRE_USERNAME", raising=False)
    monkeypatch.delenv("SABRE_PASSWORD", raising=False)
    monkeypatch.setattr(mod, "_token_cache", {"access_token": None, "expires_at": 0.0})

    scraper = SabreScraper()
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
    monkeypatch.setattr(settings, "SABRE_USERNAME", "")
    monkeypatch.setattr(settings, "SABRE_PASSWORD", "")
    monkeypatch.delenv("SABRE_USERNAME", raising=False)
    monkeypatch.delenv("SABRE_PASSWORD", raising=False)
    scraper = SabreScraper()
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
