"""Cross-Feed Discrepancy & Parity Validation Engine.

Prioritizes carrier direct website quotes as primary authoritative source of truth,
while utilizing Google Flights RPC as:
1. Validator: Measures price discrepancies, OTA markups, and fare-mix differences.
2. Fallback: Seamlessly supplies quotes when carrier portals are rate-limited or down.
"""

import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from packages.schemas.models import Airline, DiscrepancyAudit, Route


class CrossFeedDiscrepancyValidator:
    """Validates carrier direct pricing against aggregator RPC feed and selects primary observations."""

    PARITY_TOLERANCE_INR = 50.0  # Fares within +/- INR 50 are considered exact parity

    @classmethod
    def validate_and_reconcile(
        cls,
        db: Session,
        carrier_direct_quotes: List[Dict[str, Any]],
        rpc_quotes: List[Dict[str, Any]],
        route_code: str,
        travel_date: datetime.date,
        advance_days: int,
    ) -> Dict[str, Any]:
        """
        Reconciles carrier direct quotes and RPC aggregator quotes.
        1. Compares prices for matched flights.
        2. Logs DiscrepancyAudit records.
        3. Returns prioritized observations (Carrier Direct first, RPC fallback second).
        """
        route = db.query(Route).filter(Route.route_code == route_code.upper()).first()
        route_id = route.id if route else 1

        airlines = db.query(Airline).all()
        airline_code_map = {a.code: a.id for a in airlines}

        # Index carrier direct quotes by (carrier_code, flight_number or departure_time)
        direct_map: Dict[str, Dict[str, Any]] = {}
        for q in carrier_direct_quotes:
            c = q.get("carrier_code", "6E")
            f_no = str(q.get("flight_number", ""))
            dep = str(q.get("departure_time", ""))[:5]
            key = f"{c}_{f_no}" if f_no else f"{c}_{dep}"
            direct_map[key] = q

        audits: List[DiscrepancyAudit] = []
        prioritized_observations: List[Dict[str, Any]] = []

        matched_rpc_keys = set()

        # Step 1: Evaluate all Carrier Direct quotes (Priority 1)
        for d_key, d_quote in direct_map.items():
            c_code = d_quote["carrier_code"]
            a_id = airline_code_map.get(c_code, 1)
            direct_price = float(d_quote["total_fare"])
            f_no = str(d_quote.get("flight_number", f"{c_code}-101"))
            dep = str(d_quote.get("departure_time", "08:00"))[:5]

            # Find matching RPC quote
            rpc_match = None
            for r in rpc_quotes:
                r_code = r.get("carrier_code")
                r_fno = str(r.get("flight_number", ""))
                r_dep = str(r.get("departure_time", ""))[:5]

                if r_code == c_code and (
                    r_fno == f_no or r_dep == dep or f"{c_code}_{r_fno}" == d_key
                ):
                    rpc_match = r
                    matched_rpc_keys.add(f"{r_code}_{r_fno}")
                    break

            if rpc_match:
                rpc_price = float(rpc_match["total_fare"])
                diff = rpc_price - direct_price
                pct_diff = (abs(diff) / direct_price) * 100.0 if direct_price > 0 else 0.0

                if abs(diff) <= cls.PARITY_TOLERANCE_INR:
                    status = "EXACT_PARITY"
                elif diff > cls.PARITY_TOLERANCE_INR:
                    status = "AGGREGATOR_MARKUP"
                else:
                    status = "AGGREGATOR_DISCOUNT"

                notes = f"Validated against RPC feed. Difference: INR {diff:+.2f} ({pct_diff:.1f}%)"
            else:
                rpc_price = None
                diff = 0.0
                pct_diff = 0.0
                status = "DIRECT_ONLY"
                notes = "No matching RPC quote found for this specific flight timing."

            audit = DiscrepancyAudit(
                route_id=route_id,
                airline_id=a_id,
                flight_number=f_no,
                travel_date=travel_date,
                advance_purchase_days=advance_days,
                carrier_direct_price=direct_price,
                rpc_validator_price=rpc_price,
                discrepancy_amount=diff,
                discrepancy_pct=pct_diff,
                validation_status=status,
                notes=notes,
                verified_at=datetime.datetime.now(datetime.UTC),
            )
            db.add(audit)
            audits.append(audit)

            # Prioritize Carrier Direct Quote
            d_quote["feed_type"] = "CARRIER_DIRECT"
            d_quote["is_primary_source"] = True
            d_quote["validation_status"] = status
            prioritized_observations.append(d_quote)

        # Step 2: Fallback to RPC quotes for flights/carriers NOT covered by direct scrape
        fallback_count = 0
        for r_quote in rpc_quotes:
            c_code = r_quote.get("carrier_code", "6E")
            f_no = str(r_quote.get("flight_number", f"{c_code}-101"))
            key = f"{c_code}_{f_no}"

            if key not in matched_rpc_keys and not any(
                o["carrier_code"] == c_code and o.get("flight_number") == f_no
                for o in prioritized_observations
            ):
                # Activate RPC as resilient fallback
                fallback_count += 1
                r_price = float(r_quote["total_fare"])
                a_id = airline_code_map.get(c_code, 1)

                audit = DiscrepancyAudit(
                    route_id=route_id,
                    airline_id=a_id,
                    flight_number=f_no,
                    travel_date=travel_date,
                    advance_purchase_days=advance_days,
                    carrier_direct_price=None,
                    rpc_validator_price=r_price,
                    discrepancy_amount=0.0,
                    discrepancy_pct=0.0,
                    validation_status="FALLBACK_RPC_USED",
                    notes="Carrier direct website was unavailable/uncovered. Activated RPC fallback.",
                    verified_at=datetime.datetime.now(datetime.UTC),
                )
                db.add(audit)
                audits.append(audit)

                r_quote["feed_type"] = "RPC_FALLBACK"
                r_quote["is_primary_source"] = False
                r_quote["validation_status"] = "FALLBACK_RPC_USED"
                prioritized_observations.append(r_quote)

        db.commit()

        # Compute Scorecard Metrics
        evaluated = len(audits)
        parities = sum(1 for a in audits if a.validation_status == "EXACT_PARITY")
        markups = sum(1 for a in audits if a.validation_status == "AGGREGATOR_MARKUP")
        fallbacks = sum(1 for a in audits if a.validation_status == "FALLBACK_RPC_USED")

        avg_discrepancy = sum(
            a.discrepancy_pct for a in audits if a.carrier_direct_price is not None
        ) / max(1, len(carrier_direct_quotes))

        return {
            "route_code": route_code,
            "travel_date": travel_date.isoformat(),
            "advance_days": advance_days,
            "total_flights_evaluated": evaluated,
            "carrier_direct_quotes_count": len(carrier_direct_quotes),
            "rpc_fallback_quotes_count": fallbacks,
            "parity_count": parities,
            "aggregator_markup_count": markups,
            "average_discrepancy_pct": round(avg_discrepancy, 2),
            "primary_observations": prioritized_observations,
            "audits": [
                {
                    "carrier": a.airline_id,
                    "flight_number": a.flight_number,
                    "carrier_direct_price": a.carrier_direct_price,
                    "rpc_validator_price": a.rpc_validator_price,
                    "discrepancy_amount": a.discrepancy_amount,
                    "discrepancy_pct": a.discrepancy_pct,
                    "status": a.validation_status,
                }
                for a in audits
            ],
        }
