"""Record/replay test: a captured RPC payload is replayed offline.

Proves the archaeology helpers locate quote-like records inside the nested
batchexecute structure and that the drift detector keeps them labelled clean —
so a sniffing collector can be validated without a live network.
"""

import json
from pathlib import Path

from services.collectors.drift_detector import FareSchemaDriftDetector
from services.collectors.network_extractor import find_quote_candidates

FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "payloads"
    / "google_flights_rpc_sample.json"
)


def _has_core(node):
    return all(k in node for k in ("flight_number", "total_fare", "origin_airport"))


def _has_price(node):
    return isinstance(node.get("total_fare"), (int, float)) and node.get("total_fare") > 0


def test_replayed_fixture_records_are_found():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = find_quote_candidates(payload, [_has_core, _has_price])
    assert len(records) == 3
    assert {r["flight_number"] for r in records} == {"6E-205", "6E-532", "AI-806"}


def test_replayed_fixture_passes_drift_validation():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    records = find_quote_candidates(payload, [_has_core])
    report = FareSchemaDriftDetector.detect(records)
    assert report["clean_count"] == len(records)
    assert report["is_drifting"] is False
    assert records[0]["total_fare"] == 3540.0
