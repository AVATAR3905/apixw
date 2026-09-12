"""Unit tests for Data Quality Engine & Normalization (PRD Section 62)."""

from packages.statistics.normalizer import FareNormalizer
from packages.statistics.quality import QualityEngine


def test_valid_fare_accept():
    """Case 1: Valid complete fare decomposes properly -> ACCEPT."""
    obs = {
        "origin": "DEL",
        "destination": "BOM",
        "carrier": "6E",
        "flight_number": "6E-201",
        "base_fare": 4000.0,
        "fuel_surcharge": 800.0,
        "tax_amount": 250.0,
        "development_fee": 150.0,
        "convenience_fee": 300.0,
        "other_fee": 0.0,
        "total_fare": 5500.0,
        "availability_status": "AVAILABLE",
    }
    score, status, reason = QualityEngine.evaluate(obs)
    assert status == "ACCEPT"
    assert score >= 90.0
    assert reason is None


def test_sold_out_flight_handling():
    """Case 2: Sold out flight -> MISSING_FOR_INDEX (not zero, excluded from price)."""
    obs = {
        "origin": "DEL",
        "destination": "BOM",
        "carrier": "AI",
        "flight_number": "AI-102",
        "availability_status": "SOLD_OUT",
        "total_fare": None,
        "base_fare": None,
    }
    score, status, reason = QualityEngine.evaluate(obs)
    assert status == "MISSING_FOR_INDEX"
    assert "SOLD_OUT" in reason


def test_negative_or_zero_price_reject():
    """Case 3: Negative price observed -> REJECT."""
    obs = {
        "origin": "DEL",
        "destination": "BLR",
        "carrier": "SG",
        "flight_number": "SG-812",
        "base_fare": -500.0,
        "total_fare": -100.0,
    }
    score, status, reason = QualityEngine.evaluate(obs)
    assert status == "REJECT"
    assert score == 0.0


def test_missing_route_reject():
    """Case 4: Missing origin or destination -> REJECT."""
    obs = {
        "origin": "DEL",
        "destination": "DEL",  # Origin == Destination
        "carrier": "6E",
        "flight_number": "6E-101",
        "total_fare": 4500.0,
        "base_fare": 3500.0,
    }
    score, status, reason = QualityEngine.evaluate(obs)
    assert status == "REJECT"
    assert score == 0.0


def test_component_mismatch_warning():
    """Case 5: Minor component mismatch ($5 < diff <= $50) -> ACCEPT_WITH_WARNING."""
    obs = {
        "origin": "BOM",
        "destination": "BLR",
        "carrier": "QP",
        "flight_number": "QP-1301",
        "base_fare": 3000.0,
        "tax_amount": 200.0,
        "fuel_surcharge": 500.0,
        "development_fee": 100.0,
        "convenience_fee": 0.0,
        "other_fee": 0.0,
        "total_fare": 3820.0,  # 20 INR discrepancy
    }
    score, status, reason = QualityEngine.evaluate(obs)
    assert status == "ACCEPT_WITH_WARNING"
    assert 70.0 <= score < 90.0


def test_duplicate_observation_deduplicated():
    """Case 6: Duplicate detection flag -> DEDUPLICATED."""
    obs = {
        "origin": "DEL",
        "destination": "CCU",
        "carrier": "AI",
        "flight_number": "AI-401",
        "total_fare": 4500.0,
        "base_fare": 3500.0,
        "is_duplicate": True,
    }
    score, status, reason = QualityEngine.evaluate(obs)
    assert status == "DEDUPLICATED"
    assert score == 50.0


def test_extreme_price_retained_for_review():
    """Case 7: Extreme price outlier (> 60k) -> REVIEW (not deleted automatically)."""
    obs = {
        "origin": "DEL",
        "destination": "BOM",
        "carrier": "AI",
        "flight_number": "AI-805",
        "base_fare": 65000.0,
        "tax_amount": 3250.0,
        "fuel_surcharge": 1200.0,
        "development_fee": 550.0,
        "convenience_fee": 0.0,
        "other_fee": 0.0,
        "total_fare": 70000.0,
    }
    score, status, reason = QualityEngine.evaluate(obs)
    assert status == "REVIEW"
    assert score == 65.0
    assert "retained for review" in reason


def test_source_error():
    """Case 8: Source / Parser error -> SOURCE_ERROR."""
    obs = {
        "origin": "DEL",
        "destination": "BOM",
        "source_error": True,
    }
    score, status, reason = QualityEngine.evaluate(obs)
    assert status == "SOURCE_ERROR"
    assert score == 0.0


def test_normalizer_sold_out():
    """Normalizer explicitly sets base_fare to None for sold out."""
    raw = {
        "origin": "del",
        "destination": "bom",
        "carrier": "6e",
        "flight_number": "6e-101",
        "availability_status": "SOLD_OUT",
        "total_fare": 5000.0,
    }
    normalized = FareNormalizer.normalize_observation(raw)
    assert normalized["availability_status"] == "SOLD_OUT"
    assert normalized["base_fare"] is None
    assert normalized["total_fare"] is None
