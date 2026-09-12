"""Unit tests for the two-stage confidence engine."""

from packages.statistics.confidence import ConfidenceService


def test_method_weights_discount_non_network_methods():
    assert ConfidenceService.method_weight("NETWORK_XHR") > ConfidenceService.method_weight(
        "DOM_BROWSER"
    )
    assert ConfidenceService.method_weight("DOM_BROWSER") > ConfidenceService.method_weight(
        "CALIBRATED_MODEL"
    )
    assert ConfidenceService.method_weight("CALIBRATED_MODEL") > ConfidenceService.method_weight(
        "SYNTHETIC"
    )
    assert ConfidenceService.method_weight("") == 0.5  # unknown falls back to neutral


def test_composite_discounts_calibrated_model():
    live = ConfidenceService.composite(95.0, "NETWORK_XHR", agreement=1.0)
    simulated = ConfidenceService.composite(95.0, "CALIBRATED_MODEL", agreement=1.0)
    assert live > simulated
    assert simulated < 95.0


def test_composite_clamps_and_agreement_bonus():
    assert ConfidenceService.composite(100.0, "NETWORK_XHR", agreement=1.0) == 100.0
    alone = ConfidenceService.composite(80.0, "RPC", agreement=1.0)
    contested = ConfidenceService.composite(80.0, "RPC", agreement=0.0)
    assert alone > contested


def test_bands_use_configured_thresholds():
    assert ConfidenceService.band(95.0) == "HIGH"
    assert ConfidenceService.band(75.0) == "MEDIUM"
    assert ConfidenceService.band(50.0) == "LOW"


def test_cross_source_agreement():
    quotes = [
        {"total_fare": 3500.0},
        {"total_fare": 3500.0},
        {"total_fare": 3540.0},
        {"total_fare": 4300.0},  # outlier far beyond +-10% of median
    ]
    agreement = ConfidenceService.cross_source_agreement(quotes)
    assert 0.0 < agreement < 1.0
    assert ConfidenceService.cross_source_agreement([]) == 0.0


def test_score_quotes_enriches_metadata():
    quotes = [
        {"flight_number": "6E-205", "total_fare": 3500.0, "extraction_method": "NETWORK_XHR"},
        {"flight_number": "6E-205", "total_fare": 3540.0},
    ]
    scored = ConfidenceService.score_quotes(quotes)
    for row in scored:
        assert "confidence_score" in row
        assert "confidence_band" in row
        assert "cross_source_agreement" in row
    # Well-agreeing live quotes land in HIGH band.
    assert scored[0]["confidence_band"] == "HIGH"
