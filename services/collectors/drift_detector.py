"""Schema-drift alarm for parsed fare payloads.

Google Flights exposes no stable API: live fares arrive via a proprietary
batchexecute RPC whose record shape rotates without notice. This detector
validates every parsed record against the expected schema and alarms the moment
records stop conforming, so the pipeline fails loudly (or labels the feed as
drifting) instead of silently ingesting garbage.
"""

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_IATA_RE = re.compile(r"^[A-Z]{3}$")
_FLIGHT_NO_RE = re.compile(r"^[A-Z0-9]{2}-\d{3,4}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Fields every parsed fare record must carry after our normalizer.
REQUIRED_FIELDS = (
    "flight_number",
    "origin_airport",
    "destination_airport",
    "travel_date",
    "total_fare",
)

# Unexpected top-level keys strongly suggest the RPC record shape changed.
KNOWN_KEYS = set(REQUIRED_FIELDS) | {
    "carrier_code",
    "carrier_name",
    "departure_time",
    "arrival_time",
    "stops",
    "advance_purchase_days",
    "cabin_class",
    "fare_family",
    "base_fare",
    "fuel_surcharge",
    "tax_amount",
    "development_fee",
    "convenience_fee",
    "other_fee",
    "currency",
    "availability_status",
    "feed_type",
    "extraction_method",
    "source",
}


class FareSchemaDriftDetector:
    """Validates parsed fare records and emits a drift report."""

    @classmethod
    def validate_record(cls, record: Dict[str, Any]) -> List[str]:
        """Return a list of schema violations for a single parsed fare record."""
        issues: List[str] = []
        for field in REQUIRED_FIELDS:
            if field not in record or record.get(field) in (None, ""):
                issues.append(f"missing_required_field:{field}")
                continue
            value = record[field]
            if field == "origin_airport" and not _IATA_RE.match(str(value)):
                issues.append(f"bad_iata:{field}={value}")
            elif field == "destination_airport" and not _IATA_RE.match(str(value)):
                issues.append(f"bad_iata:{field}={value}")
            elif field == "travel_date" and not _DATE_RE.match(str(value)):
                issues.append(f"bad_date:{field}={value}")
            elif field == "flight_number" and not _FLIGHT_NO_RE.match(str(value)):
                issues.append(f"bad_flight_number:{value}")
            elif field == "total_fare":
                try:
                    total = float(value)
                    if not (0 < total <= 200000):
                        issues.append(f"out_of_range:total_fare={value}")
                except (TypeError, ValueError):
                    issues.append(f"non_numeric:total_fare={value}")

        total = cls._num(record.get("total_fare"))
        base = cls._num(record.get("base_fare"))
        if total is not None and base is not None and base > total:
            issues.append(f"base_fare_gt_total:base={base},total={total}")

        unknown = set(record.keys()) - KNOWN_KEYS
        if unknown:
            issues.append(f"unexpected_keys:{sorted(unknown)}")
        return issues

    @staticmethod
    def _num(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def detect(cls, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a batch of parsed records and return a drift report."""
        clean_count, problems = 0, []
        for record in records:
            issues = cls.validate_record(record)
            if not issues:
                clean_count += 1
            else:
                problems.append(
                    {
                        "flight_number": record.get("flight_number"),
                        "travel_date": record.get("travel_date"),
                        "issues": issues,
                    }
                )

        drift_count = len(problems)
        is_drifting = drift_count > max(2, int(len(records) * 0.1)) if records else False
        report = {
            "records_checked": len(records),
            "clean_count": clean_count,
            "drift_count": drift_count,
            "is_drifting": is_drifting,
            "sample_problems": problems[:10],
        }
        if is_drifting:
            logger.error(
                "FARE_SCHEMA_DRIFT detected on %d/%d records.",
                drift_count,
                len(records),
            )
        return report

    @classmethod
    def raise_if_drifting(cls, report: Dict[str, Any]) -> None:
        """Hard-fail on total schema collapse (every record invalid)."""
        checked = report.get("records_checked") or 0
        if checked and report.get("drift_count") == checked and checked > 0:
            from services.collectors.circuit_breaker import CollectorErrorCode, CollectorException

            raise CollectorException(
                code=CollectorErrorCode.SCHEMA_CHANGED,
                message="Fare schema drift detected: all parsed records failed validation.",
            )


_LAST_DRIFT_REPORT: Dict[str, Any] = {}


def record_drift(report: Dict[str, Any]) -> None:
    """Store the latest drift report globally for operator inspection."""
    global _LAST_DRIFT_REPORT
    _LAST_DRIFT_REPORT = report


def latest_drift_report() -> Dict[str, Any]:
    return dict(_LAST_DRIFT_REPORT)
