"""Real-world Fare Normalizer and Section 62 Quality Gate (PRD Section 26, 62)."""

import datetime
import logging
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from packages.schemas.models import Airline, FareObservation, Route, Source
from packages.statistics.quality import QualityEngine

logger = logging.getLogger(__name__)

OTA_SOURCE_NAMES = {
    "MakeMyTrip India",
    "Ixigo Flights",
    "EaseMyTrip",
    "Yatra Online",
    "Cleartrip",
    "Skyscanner India",
}


class RealFareNormalizer:
    """Normalizes real flight quotes, breaks down fare components, and applies Section 62 quality filters."""

    @classmethod
    def normalize_and_persist_observations(
        cls,
        db: Session,
        raw_quotes: List[Dict[str, Any]],
        route_code: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> List[FareObservation]:
        """
        Processes real quotes through Section 62 quality rules, applies fare decomposition,
        flags carrier minimum fares, and persists to fare_observations.
        """
        route = db.query(Route).filter(Route.route_code == route_code.upper()).first()
        if not route:
            raise ValueError(f"Route {route_code} not found in database.")

        sources = db.query(Source).all()
        source_map = {s.name: s.id for s in sources}
        carrier_source_id = source_map.get("Carrier Direct Booking Scraper", 5)
        rpc_source_id = source_map.get("Google Flights RPC Validator & Fallback", 6)
        ota_source_ids = {
            name: sid for name, sid in source_map.items() if name in OTA_SOURCE_NAMES
        } or {}

        airlines = db.query(Airline).all()
        airline_map = {a.code: a.id for a in airlines}

        persisted: List[FareObservation] = []
        carrier_quotes: Dict[str, List[FareObservation]] = {}

        now = datetime.datetime.now(datetime.UTC)

        for q in raw_quotes:
            try:
                total = float(q.get("total_fare", 0.0))
            except (TypeError, ValueError):
                logger.warning(
                    "Skipping malformed quote (non-numeric total_fare=%r): %s",
                    q.get("total_fare"), q.get("flight_number", "?"),
                )
                continue

            # PRD Section 62 Rule: Valid fare bounds
            if not (1500.0 <= total <= 60000.0):
                continue

            c_code = q.get("carrier_code")
            if not c_code:
                logger.warning("Skipping quote with no carrier_code: %s", q.get("flight_number", "?"))
                continue
            a_id = airline_map.get(c_code, 1)

            try:
                # Prefer a genuine fare decomposition when the collector already
                # extracted one from the source (e.g. SpiceJet's real
                # base/publishedFare split via NETWORK_API), so real observations
                # aren't silently overwritten by the estimation formula below.
                has_real_decomposition = (
                    q.get("extraction_method") == "NETWORK_API" and q.get("base_fare") is not None
                )
                if has_real_decomposition:
                    base = round(float(q["base_fare"]), 2)
                    fuel = round(float(q.get("fuel_surcharge", 0.0)), 2)
                    gst = round(float(q.get("tax_amount", 0.0)), 2)
                    udf = round(float(q.get("development_fee", 0.0)), 2)
                    conv_fee = round(float(q.get("convenience_fee", 0.0)), 2)
                else:
                    # Fare Decomposition (Estimating statutory breakdown if total fare is unified)
                    # GST: 5% on base + fuel
                    # UDF / Airport Fee: ~INR 350 - 450
                    # Convenience Fee: ~INR 299
                    # Fuel Surcharge: ~15%
                    # Base Fare: Remaining (~70%)
                    udf = 350.0
                    conv_fee = (
                        299.0 if q.get("feed_type") == "RPC_FALLBACK" else 0.0
                    )  # Direct booking saves convenience fee
                    net_airline_revenue = max(500.0, total - udf - conv_fee)
                    gst = round(net_airline_revenue * 0.05, 2)
                    fuel = round(net_airline_revenue * 0.15, 2)
                    base = round(net_airline_revenue - gst - fuel, 2)

                feed_type = q.get("feed_type", "CARRIER_DIRECT")
                if feed_type == "CARRIER_DIRECT":
                    s_id = carrier_source_id
                elif feed_type in ("OTA_AGGREGATOR", "PARTNER_API"):
                    # OTA scrapers and licensed GDS adapters embed their
                    # registry source_id on each quote; prefer it, falling
                    # back to the name map (both align with the seed registry).
                    src_name = q.get("source_name", "")
                    s_id = int(
                        q.get("source_id")
                        or ota_source_ids.get(src_name, rpc_source_id)
                    )
                else:
                    s_id = rpc_source_id
            except (TypeError, ValueError, KeyError) as e:
                logger.warning(
                    "Skipping malformed quote (%s): %s", e, q.get("flight_number", "?")
                )
                continue

            availability_status = str(q.get("availability_status", "AVAILABLE")).upper()

            # Actually run the Section 62 quality gate instead of stamping a
            # fixed score -- this previously hardcoded quality_score=98.5 /
            # quality_status="ACCEPT" on every real observation regardless of
            # content, which meant QualityEngine's real checks (route
            # validity, fare-decomposition-sum consistency, plausible-range
            # review, sold-out handling) never actually ran on real data, and
            # /api/v1/data-quality's "rejected_quotes_count" was structurally
            # always 0 -- not because nothing was ever bad, but because
            # nothing was ever checked.
            quality_score, quality_status, quality_reason = QualityEngine.evaluate(
                {
                    "origin": route.origin_airport,
                    "destination": route.destination_airport,
                    "carrier": c_code,
                    "availability_status": availability_status,
                    "total_fare": total,
                    "base_fare": base,
                    "fuel_surcharge": fuel,
                    "tax_amount": gst,
                    "development_fee": udf,
                    "convenience_fee": conv_fee,
                    "other_fee": 0.0,
                }
            )
            if quality_reason:
                logger.info(
                    "Quality gate %s (%.1f) for %s %s: %s",
                    quality_status, quality_score, c_code,
                    q.get("flight_number", "?"), quality_reason,
                )

            obs = FareObservation(
                source_id=s_id,
                route_id=route.id,
                airline_id=a_id,
                search_timestamp=now,
                travel_date=travel_date,
                advance_purchase_days=advance_days,
                flight_number=q.get("flight_number", f"{c_code}-101"),
                cabin_class="ECONOMY",
                fare_family="BASIC",
                stops=q.get("stops", 0),
                availability_status=availability_status,
                is_carrier_min_fare=False,  # Will be calculated below
                base_fare=base,
                fuel_surcharge=fuel,
                tax_amount=gst,
                development_fee=udf,
                convenience_fee=conv_fee,
                other_fee=0.0,
                total_fare=total,
                currency="INR",
                # Only genuinely scraped/RPC quotes are real; a calibrated
                # fallback that reached this path (browser blocked/unavailable)
                # must stay flagged synthetic, never silently promoted to real.
                is_synthetic=feed_type in ("CALIBRATED_BASELINE", "SYNTHETIC_BASELINE")
                or q.get("extraction_method") == "CALIBRATED_MODEL",
                feed_type=feed_type,
                extraction_method=q.get(
                    "extraction_method", "RPC" if feed_type == "RPC_FALLBACK" else "NETWORK"
                ),
                quality_score=quality_score,
                quality_status=quality_status,
                collector_version="2.0.0",
                schema_version="2.0.0",
                created_at=now,
            )
            db.add(obs)
            persisted.append(obs)

            if c_code not in carrier_quotes:
                carrier_quotes[c_code] = []
            carrier_quotes[c_code].append(obs)

        # Flag lowest-economy quote per carrier (Fare-Mix Protection); never
        # let a SOLD_OUT placeholder or zero-fare row win the "cheapest" flag.
        for c_code, obs_list in carrier_quotes.items():
            priced = [o for o in obs_list if o.base_fare and o.base_fare > 0]
            cheapest = min(priced, key=lambda x: x.base_fare) if priced else None
            if cheapest is not None:
                cheapest.is_carrier_min_fare = True

        db.commit()
        return persisted
