"""Unit tests for the fare schema drift detector."""

import pytest

from services.collectors.circuit_breaker import CollectorErrorCode, CollectorException
from services.collectors.drift_detector import (
    FareSchemaDriftDetector,
    latest_drift_report,
    record_drift,
)


def _valid_record():
    return {
        "flight_number": "6E-205",
        "origin_airport": "DEL",
        "destination_airport": "BOM",
        "travel_date": "2026-09-18",
        "total_fare": 3540.0,
        "carrier_code": "6E",
        "carrier_name": "IndiGo",
    }


def test_valid_record_has_no_issues():
    assert FareSchemaDriftDetector.validate_record(_valid_record()) == []


def test_missing_required_field():
    record = _valid_record()
    record.pop("total_fare")
    issues = FareSchemaDriftDetector.validate_record(record)
    assert "missing_required_field:total_fare" in issues


def test_bad_iata_and_date_and_flight_number():
    record = _valid_record()
    record["origin_airport"] = "DELHI"
    record["travel_date"] = "18/09/2026"
    record["flight_number"] = "205"
    issues = FareSchemaDriftDetector.validate_record(record)
    assert any(i.startswith("bad_iata:") for i in issues)
    assert any(i.startswith("bad_date:") for i in issues)
    assert any(i.startswith("bad_flight_number:") for i in issues)


def test_base_fare_above_total_flagged():
    record = _valid_record()
    record["base_fare"] = 8000.0
    issues = FareSchemaDriftDetector.validate_record(record)
    assert any(i.startswith("base_fare_gt_total:") for i in issues)


def test_unexpected_keys_flagged_for_schema_shift():
    record = _valid_record()
    record["gri_encoded_layout"] = "rotated"
    issues = FareSchemaDriftDetector.validate_record(record)
    assert any(i.startswith("unexpected_keys:") for i in issues)


def test_detect_flags_drift_when_mostly_invalid():
    records = [_valid_record() for _ in range(4)] + [
        {"flight_number": "X", "total_fare": -5} for _ in range(6)
    ]
    report = FareSchemaDriftDetector.detect(records)
    assert report["records_checked"] == 10
    assert report["drift_count"] >= 6
    assert report["is_drifting"] is True


def test_raise_if_drifting_full_collapse():
    records = [{"no": "fields"} for _ in range(3)]
    report = FareSchemaDriftDetector.detect(records)
    with pytest.raises(CollectorException) as exc:
        FareSchemaDriftDetector.raise_if_drifting(report)
    assert exc.value.code == CollectorErrorCode.SCHEMA_CHANGED


def test_record_drift_store():
    report = FareSchemaDriftDetector.detect([_valid_record()])
    record_drift(report)
    assert latest_drift_report()["clean_count"] == 1
