"""Multi-OTA Source-Pair Markup Audit Engine (Phase 2).

Computes and persists pairwise price discrepancies — any source against an
authoritative reference (carrier-direct if present, else the cheapest observed
OTA price) — for the *same physical flight entity* across the multi-source
orchestration pipeline. Persists into ``discrepancy_audits`` with
``audit_type == OTA_SOURCE_PAIR`` so the legacy binary cross-feed audit rows
(CARRIER_DIRECT vs RPC) remain intact and comparable.
"""

import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import Airline, DiscrepancyAudit, Route
from packages.shared.time_utils import utcnow
from packages.statistics.flight_matcher import FlightEntityMatcher

MARKUP_TRIGGER_INR = 50.0


class SourcePairAuditor:
    """Computes source-pair markup audits over multi-OTA flight clusters."""

    REFERENCE_FEED_TYPES = ("CARRIER_DIRECT",)

    @classmethod
    def _route_id(cls, db: Session, route_code: str) -> int:
        route = db.query(Route).filter(Route.route_code == route_code.upper()).first()
        return route.id if route else 1

    @classmethod
    def _airline_map(cls, db: Session) -> Dict[str, int]:
        return {a.code: a.id for a in db.query(Airline).all()}

    @classmethod
    def _reference_quote(cls, cluster: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Returns the authoritative reference quote for a cluster.

        Prefers the carrier-direct quote (feed_type CARRIER_DIRECT or source_id 5);
        otherwise the cheapest observed quote (minimum-walkaway benchmark).
        """
        direct = [
            q
            for q in cluster["all_quotes"]
            if q.get("feed_type") == "CARRIER_DIRECT" or q.get("source_id") == 5
        ]
        if direct:
            return min(direct, key=lambda q: float(q.get("total_fare", 0)))
        priced = [
            q for q in cluster["all_quotes"] if q.get("total_fare") and float(q["total_fare"]) > 0
        ]
        if not priced:
            return None
        return min(priced, key=lambda q: float(q["total_fare"]))

    @classmethod
    def audit_source_pairs(
        cls,
        db: Session,
        quotes: List[Dict[str, Any]],
        route_code: str,
        travel_date: datetime.date,
        advance_days: int,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Persists OTA_SOURCE_PAIR discrepancy audits for every source vs the
        authoritative reference within each matched flight entity.

        Returns a scorecard: counts by status plus the raw audit rows.
        """
        route_id = cls._route_id(db, route_code)
        airline_map = cls._airline_map(db)
        audits: List[DiscrepancyAudit] = []

        clusters = FlightEntityMatcher.cluster_common_flights(quotes)

        markup_count = 0
        parity_count = 0
        discount_count = 0
        pairs_evaluated = 0

        for cluster in clusters.values():
            reference = cls._reference_quote(cluster)
            if reference is None:
                continue
            ref_price = float(reference["total_fare"])
            ref_id = reference.get("source_id")
            ref_name = reference.get("source_name", "Unknown")
            ref_feed = reference.get("feed_type", "OTA_AGGREGATOR")

            # De-duplicate sources so a single source only appears once per flight
            seen_sources = set()
            for quote in cluster["all_quotes"]:
                src_id = quote.get("source_id")
                src_name = quote.get("source_name", "Unknown")
                if (src_id, src_name) == (ref_id, ref_name):
                    continue
                dedup_key = src_id if src_id is not None else src_name
                if dedup_key in seen_sources:
                    continue
                seen_sources.add(dedup_key)

                try:
                    price = float(quote["total_fare"])
                except (KeyError, TypeError, ValueError):
                    continue
                if price <= 0:
                    continue

                pairs_evaluated += 1
                markup = round(price - ref_price, 2)
                markup_pct = round((markup / ref_price) * 100.0, 2) if ref_price > 0 else 0.0

                if abs(markup) <= MARKUP_TRIGGER_INR:
                    status = "EXACT_PARITY"
                    parity_count += 1
                elif markup > MARKUP_TRIGGER_INR:
                    status = "AGGREGATOR_MARKUP"
                    markup_count += 1
                else:
                    status = "AGGREGATOR_DISCOUNT"
                    discount_count += 1

                audit = DiscrepancyAudit(
                    route_id=route_id,
                    airline_id=airline_map.get(quote.get("carrier_code", "6E"), 1),
                    flight_number=str(cluster["flight_number"]),
                    travel_date=travel_date,
                    advance_purchase_days=advance_days,
                    discrepancy_amount=markup,
                    discrepancy_pct=abs(markup_pct),
                    validation_status=status,
                    audit_type="OTA_SOURCE_PAIR",
                    source_a_id=int(ref_id) if ref_id is not None else None,
                    source_b_id=int(src_id) if src_id is not None else None,
                    source_a_name=ref_name,
                    source_b_name=src_name,
                    feed_type_a=ref_feed,
                    feed_type_b=quote.get("feed_type", "OTA_AGGREGATOR"),
                    price_a=ref_price,
                    price_b=price,
                    markup_amount=markup,
                    markup_pct=markup_pct,
                    notes=(
                        f"Pair audit: {ref_name} -> {src_name} "
                        f"markup INR {markup:+.2f} ({markup_pct:+.2f}%)"
                    ),
                    verified_at=utcnow(),
                )
                audits.append(audit)

        if persist:
            db.add_all(audits)
            db.commit()

        return {
            "route_code": route_code.upper(),
            "travel_date": travel_date.isoformat(),
            "advance_days": advance_days,
            "airlines_evaluated": len(clusters),
            "pairs_evaluated": pairs_evaluated,
            "markup_count": markup_count,
            "parity_count": parity_count,
            "discount_count": discount_count,
            "audited_rows": [
                {
                    "flight_number": a.flight_number,
                    "source_a": a.source_a_name,
                    "source_b": a.source_b_name,
                    "source_pair": (
                        f"{a.source_a_name} / {a.source_b_name}"
                        if a.source_a_name and a.source_b_name
                        else None
                    ),
                    "feed_type_b": a.feed_type_b,
                    "price_a": a.price_a,
                    "price_b": a.price_b,
                    "markup_amount": a.markup_amount,
                    "markup_pct": a.markup_pct,
                    "status": a.validation_status,
                }
                for a in audits
            ],
        }
