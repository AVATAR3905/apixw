"""One-time merge of AyushyaRanjan/APIx's real cleaned Ixigo fare data
(exports/real_cleaned_fares.csv, 2026-09-13 to 09-15) into our own
fare_observations table.

Scope, deliberately conservative:
- Only the 6 routes that map directly (same directionality) onto our own
  tracked basket: BLR-HYD, BOM-BLR, DEL-BLR, DEL-BOM, DEL-CCU, DEL-HYD.
- Excluded: BOM-CCU, BOM-HYD, CCU-BLR (not in our basket at all) and
  MAA-DEL (the reverse direction of our DEL-MAA route -- not silently
  treated as equivalent; a return-leg fare isn't assumed identical to the
  outbound fare without a deliberate methodology decision).
- Reuses the exact same fare-decomposition estimate and QualityEngine gate
  every other real observation in this project goes through (mirrors
  services/collectors/real_fare_normalizer.py's non-network-api branch),
  so imported rows are held to the identical bar, not silently trusted.
- search_timestamp is set to the ACTUAL historical fetch time (joined from
  real_raw_quotes.csv's fetched_at), not "now" -- this is real historical
  data from 2026-09-13/14/15, and must not be misrepresented as collected
  today.
- Tagged with a distinct collector_version so the import is traceable and
  auditable, never silently indistinguishable from our own live collection.
"""
import csv
import datetime
import hashlib
import json
import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, ".."))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)  # so database/session.py's relative sqlite path resolves correctly

from database.session import SessionLocal
from packages.schemas.models import Airline, FareObservation, RawPayload, Route, Source
from packages.statistics.quality import QualityEngine

IMPORT_SOURCE_COMMIT = "AyushyaRanjan/APIx@main (final commit, 2026-09-29)"
COLLECTOR_VERSION = "EXTERNAL_IMPORT:AyushyaRanjan-APIx"
SCHEMA_VERSION = "1.0"

# (friend_origin, friend_destination) -> our route_code. Deliberately excludes
# BOM-CCU / BOM-HYD / CCU-BLR (not in our basket) and MAA-DEL (reverse
# direction of our DEL-MAA route, not assumed equivalent).
ROUTE_MAP = {
    ("BLR", "HYD"): "BLR-HYD",
    ("BOM", "BLR"): "BOM-BLR",
    ("DEL", "BLR"): "DEL-BLR",
    ("DEL", "BOM"): "DEL-BOM",
    ("DEL", "CCU"): "DEL-CCU",
    ("DEL", "HYD"): "DEL-HYD",
}


def load_fetched_at_by_raw_id():
    fetched_at = {}
    with open(os.path.join(THIS_DIR, "real_raw_quotes.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            fetched_at[row["id"]] = row["fetched_at"]
    return fetched_at


def estimate_decomposition(total: float) -> dict:
    """Mirrors real_fare_normalizer.py's estimate branch exactly (used
    whenever a collector -- ours or this imported one -- only has a total
    fare, no real breakdown)."""
    udf = 350.0
    conv_fee = 0.0  # OTA feed, matches the existing formula's non-RPC branch
    net_airline_revenue = max(500.0, total - udf - conv_fee)
    gst = round(net_airline_revenue * 0.05, 2)
    fuel = round(net_airline_revenue * 0.15, 2)
    base = round(net_airline_revenue - gst - fuel, 2)
    return {
        "base_fare": base,
        "fuel_surcharge": fuel,
        "tax_amount": gst,
        "development_fee": udf,
        "convenience_fee": conv_fee,
    }


def main():
    fetched_at_by_raw_id = load_fetched_at_by_raw_id()

    db = SessionLocal()
    try:
        routes_by_code = {r.route_code: r for r in db.query(Route).all()}
        airlines_by_code = {a.code: a for a in db.query(Airline).all()}
        ixigo_source = db.query(Source).filter(Source.name == "Ixigo Flights").first()
        if not ixigo_source:
            raise RuntimeError("'Ixigo Flights' source not found in our sources table.")

        # Raw payload provenance: one shared RawPayload row pointing at the
        # source export, so every imported observation stays traceable to
        # where it actually came from (never fabricated, always auditable).
        payload_note = json.dumps(
            {"imported_from": IMPORT_SOURCE_COMMIT, "file": "exports/real_cleaned_fares.csv"}
        )
        payload_hash = hashlib.sha256(payload_note.encode("utf-8")).hexdigest()
        raw_payload = RawPayload(
            source_id=ixigo_source.id,
            payload_uri="https://raw.githubusercontent.com/AyushyaRanjan/APIx/main/exports/real_cleaned_fares.csv",
            payload_hash=payload_hash,
            content_type="text/csv",
            captured_at=datetime.datetime.now(datetime.UTC),
        )
        db.add(raw_payload)
        db.flush()

        inserted = 0
        skipped_out_of_basket = 0
        skipped_reverse_direction = 0
        skipped_quality = 0
        by_status = {}

        with open(os.path.join(THIS_DIR, "real_cleaned_fares.csv"), encoding="utf-8") as f:
            for row in csv.DictReader(f):
                key = (row["origin_iata"], row["destination_iata"])
                if key == ("MAA", "DEL"):
                    skipped_reverse_direction += 1
                    continue
                route_code = ROUTE_MAP.get(key)
                if not route_code:
                    skipped_out_of_basket += 1
                    continue
                route = routes_by_code[route_code]

                carrier_code = row["carrier_iata"]
                airline = airlines_by_code.get(carrier_code)
                if not airline:
                    continue

                total = float(row["total_fare_inr"])
                decomp = estimate_decomposition(total)

                quality_score, quality_status, quality_reason = QualityEngine.evaluate(
                    {
                        "origin": route.origin_airport,
                        "destination": route.destination_airport,
                        "carrier": carrier_code,
                        "availability_status": "AVAILABLE",
                        "total_fare": total,
                        **decomp,
                        "other_fee": 0.0,
                    }
                )
                by_status[quality_status] = by_status.get(quality_status, 0) + 1
                if quality_status == "REJECT":
                    skipped_quality += 1
                    continue

                fetched_at_raw = fetched_at_by_raw_id.get(row["raw_quote_id"], row["cleaned_at"])
                search_timestamp = datetime.datetime.fromisoformat(
                    fetched_at_raw.replace("+00", "+00:00") if fetched_at_raw.endswith("+00") else fetched_at_raw
                )
                travel_date = datetime.date.fromisoformat(row["travel_date"])

                obs = FareObservation(
                    source_id=ixigo_source.id,
                    route_id=route.id,
                    airline_id=airline.id,
                    search_timestamp=search_timestamp,
                    travel_date=travel_date,
                    advance_purchase_days=int(row["advance_purchase_days"]),
                    flight_number=row["flight_number"],
                    cabin_class="ECONOMY",
                    fare_family="BASIC",
                    stops=0,
                    availability_status="AVAILABLE",
                    is_carrier_min_fare=False,
                    base_fare=decomp["base_fare"],
                    fuel_surcharge=decomp["fuel_surcharge"],
                    tax_amount=decomp["tax_amount"],
                    development_fee=decomp["development_fee"],
                    convenience_fee=decomp["convenience_fee"],
                    other_fee=0.0,
                    total_fare=total,
                    currency="INR",
                    is_synthetic=False,
                    feed_type="OTA_AGGREGATOR",
                    quality_score=quality_score,
                    quality_status=quality_status,
                    collector_version=COLLECTOR_VERSION,
                    schema_version=SCHEMA_VERSION,
                    raw_payload_id=raw_payload.id,
                    extraction_method="EXTERNAL_IMPORT",
                    created_at=datetime.datetime.now(datetime.UTC),
                )
                db.add(obs)
                inserted += 1

        db.commit()
        print(f"Inserted: {inserted}")
        print(f"Skipped (out of basket): {skipped_out_of_basket}")
        print(f"Skipped (reverse-direction MAA-DEL): {skipped_reverse_direction}")
        print(f"Skipped (quality REJECT): {skipped_quality}")
        print(f"Quality status breakdown: {by_status}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
