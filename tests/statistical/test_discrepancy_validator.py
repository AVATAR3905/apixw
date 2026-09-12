"""Statistical Unit Tests for Cross-Feed Discrepancy & Parity Validation."""

import datetime

import pytest

from database.session import SessionLocal
from packages.statistics.discrepancy_validator import CrossFeedDiscrepancyValidator


@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()


def test_cross_feed_exact_parity(db_session):
    """Verifies that flights with price difference <= INR 50 are categorized as EXACT_PARITY."""
    carrier_quotes = [
        {
            "carrier_code": "6E",
            "flight_number": "6E-501",
            "departure_time": "09:00",
            "total_fare": 4500.0,
        }
    ]
    rpc_quotes = [
        {
            "carrier_code": "6E",
            "flight_number": "6E-501",
            "departure_time": "09:00",
            "total_fare": 4520.0,  # Difference +20 <= 50
        }
    ]

    res = CrossFeedDiscrepancyValidator.validate_and_reconcile(
        db=db_session,
        carrier_direct_quotes=carrier_quotes,
        rpc_quotes=rpc_quotes,
        route_code="DEL-BOM",
        travel_date=datetime.date(2026, 9, 20),
        advance_days=15,
    )

    assert res["parity_count"] == 1
    assert res["audits"][0]["status"] == "EXACT_PARITY"
    assert res["primary_observations"][0]["feed_type"] == "CARRIER_DIRECT"


def test_cross_feed_aggregator_markup(db_session):
    """Verifies that flights where RPC price > carrier direct by > INR 50 are flagged as AGGREGATOR_MARKUP."""
    carrier_quotes = [
        {
            "carrier_code": "SG",
            "flight_number": "SG-8161",
            "departure_time": "14:00",
            "total_fare": 4000.0,
        }
    ]
    rpc_quotes = [
        {
            "carrier_code": "SG",
            "flight_number": "SG-8161",
            "departure_time": "14:00",
            "total_fare": 4350.0,  # Markup +350 (Convenience fee)
        }
    ]

    res = CrossFeedDiscrepancyValidator.validate_and_reconcile(
        db=db_session,
        carrier_direct_quotes=carrier_quotes,
        rpc_quotes=rpc_quotes,
        route_code="DEL-BOM",
        travel_date=datetime.date(2026, 9, 20),
        advance_days=15,
    )

    assert res["aggregator_markup_count"] == 1
    assert res["audits"][0]["status"] == "AGGREGATOR_MARKUP"
    assert res["audits"][0]["discrepancy_amount"] == 350.0


def test_cross_feed_rpc_fallback_activation(db_session):
    """Verifies that when carrier direct scrape has no quotes for a carrier, RPC quotes are seamlessly activated as fallback."""
    carrier_quotes = []  # Carrier site was blocked or returned empty
    rpc_quotes = [
        {
            "carrier_code": "QP",
            "flight_number": "QP-101",
            "departure_time": "18:00",
            "total_fare": 5200.0,
        }
    ]

    res = CrossFeedDiscrepancyValidator.validate_and_reconcile(
        db=db_session,
        carrier_direct_quotes=carrier_quotes,
        rpc_quotes=rpc_quotes,
        route_code="DEL-BOM",
        travel_date=datetime.date(2026, 9, 20),
        advance_days=15,
    )

    assert res["rpc_fallback_quotes_count"] == 1
    assert res["audits"][0]["status"] == "FALLBACK_RPC_USED"
    assert res["primary_observations"][0]["feed_type"] == "RPC_FALLBACK"
