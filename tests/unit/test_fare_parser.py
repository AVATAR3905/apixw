"""Unit tests for FareParser and Schema Drift detection."""

import pytest

from services.collectors.circuit_breaker import CollectorErrorCode, CollectorException
from services.collectors.fare_parser import FareParser


def test_fare_parser_valid_response():
    """Parses standard flight payload and decomposes fare components."""
    payload = {
        "status": "OK",
        "route": "DEL-BOM",
        "advance_days": 15,
        "flights": [
            {
                "carrier": "6E",
                "flight_number": "6E-205",
                "cabin_class": "ECONOMY",
                "fare_family": "BASIC",
                "base_fare": 4000.0,
                "fuel_surcharge": 850.0,
                "tax_amount": 242.5,
                "development_fee": 350.0,
                "convenience_fee": 299.0,
                "total_fare": 5741.5,
                "stops": 0,
            }
        ],
    }

    quotes = FareParser.parse_search_response(payload, route_code="DEL-BOM", advance_days=15)
    assert len(quotes) == 1
    q = quotes[0]
    assert q["carrier"] == "6E"
    assert q["flight_number"] == "6E-205"
    assert q["base_fare"] == 4000.0
    assert q["total_fare"] == 5741.5
    assert q["availability_status"] == "AVAILABLE"


def test_fare_parser_sold_out_detection():
    """Explicitly detects sold out badges and sets base_fare to None."""
    payload = {
        "status": "OK",
        "route": "DEL-BLR",
        "advance_days": 1,
        "flights": [
            {
                "carrier": "AI",
                "flight_number": "AI-504",
                "is_sold_out": True,
                "total_fare": 0.0,
            }
        ],
    }

    quotes = FareParser.parse_search_response(payload, route_code="DEL-BLR", advance_days=1)
    assert len(quotes) == 1
    assert quotes[0]["availability_status"] == "SOLD_OUT"
    assert quotes[0]["base_fare"] is None
    assert quotes[0]["total_fare"] is None


def test_fare_parser_schema_drift_detection():
    """Detects malformed/corrupted flight objects and raises SCHEMA_CHANGED error."""
    payload = {
        "status": "OK",
        "route": "DEL-BOM",
        "advance_days": 7,
        "flights": [
            {
                # Missing carrier and flight number entirely
                "some_random_corrupt_field": 12345,
            }
        ],
    }

    with pytest.raises(CollectorException) as exc_info:
        FareParser.parse_search_response(payload, route_code="DEL-BOM", advance_days=7)

    assert exc_info.value.code == CollectorErrorCode.SCHEMA_CHANGED
    assert "Schema drift detected" in str(exc_info.value)
