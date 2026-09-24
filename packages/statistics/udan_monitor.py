"""UDAN Scheme affordability monitoring (APIX-2.2 Governance Intelligence).

DEL-IXS and DEL-DHM are UDAN-subsidised regional routes.  MoCA's UDAN scheme was
launched with an affordability promise (a 1-hour flight at roughly Rs 2,500).
This module compares UDAN-route fare levels and trends against trunk routes and
the scheme's stated affordability target, flagging breaches — the first automated
affordability monitor for UDAN pricing.
"""

import datetime
import statistics
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import FareObservation, Route

UDAN_TARGET_INR = 2500.0
BREACH_MULTIPLIER = 1.5  # fare > 1.5x target / trunk median = breach flag


class UDANMonitor:
    """Tracks UDAN-route affordability relative to trunk routes and scheme targets."""

    @classmethod
    def monitor(
        cls,
        db: Session,
        observation_date: Optional[datetime.date] = None,
        horizon_days: int = 15,
        lookback_days: int = 7,
    ) -> Dict[str, Any]:
        udan_routes = (
            db.query(Route)
            .filter(Route.active, Route.corridor_type == "REGIONAL_THIN")
            .all()
        )
        trunk_routes = (
            db.query(Route)
            .filter(Route.active, Route.corridor_type == "METRO_TRUNK")
            .all()
        )

        if not udan_routes:
            return {"status": "NO_UDAN_ROUTES", "routes": []}

        trunk_fares = []
        for r in trunk_routes:
            fares = cls._route_fares(db, r.id, observation_date, horizon_days, lookback_days)
            trunk_fares.extend(fares)

        trunk_median = statistics.median(trunk_fares) if trunk_fares else None
        trunk_avg = statistics.mean(trunk_fares) if trunk_fares else 0.0

        reports: List[Dict[str, Any]] = []
        for route in udan_routes:
            fares = cls._route_fares(db, route.id, observation_date, horizon_days, lookback_days)
            if not fares:
                reports.append(
                    {
                        "route_code": route.route_code,
                        "status": "NO_RECENT_DATA",
                        "affordable": None,
                    }
                )
                continue

            latest_fare = min(fares)  # affordability is measured at the cheapest quote
            latest_date = cls._latest_quote_date(db, route.id, observation_date, horizon_days)
            ratio_vs_target = latest_fare / UDAN_TARGET_INR if UDAN_TARGET_INR else None
            ratio_vs_trunk = latest_fare / trunk_median if trunk_median else None

            breach_target = ratio_vs_target is not None and ratio_vs_target > BREACH_MULTIPLIER
            breach_trunk = ratio_vs_trunk is not None and ratio_vs_trunk > BREACH_MULTIPLIER

            if breach_target or breach_trunk:
                status = "BREACH"
            elif ratio_vs_target is not None and ratio_vs_target > 1.0:
                status = "ELEVATED"
            else:
                status = "AFFORDABLE"

            reports.append(
                {
                    "route_code": route.route_code,
                    "origin": route.origin,
                    "destination": route.destination,
                    "corridor_type": route.corridor_type,
                    "latest_fare": round(latest_fare, 2),
                    "latest_quote_date": latest_date,
                    "fare_period_avg": round(statistics.mean(fares), 2),
                    "trunk_median_fare": round(trunk_median, 2) if trunk_median else None,
                    "ratio_vs_udan_target": round(ratio_vs_target, 2) if ratio_vs_target else None,
                    "ratio_vs_trunk": round(ratio_vs_trunk, 2) if ratio_vs_trunk else None,
                    "status": status,
                }
            )

        breaches = [r["route_code"] for r in reports if r.get("status") == "BREACH"]

        return {
            "status": "COMPLETED",
            "observation_date": (observation_date or datetime.date.today()).isoformat(),
            "horizon_days": horizon_days,
            "lookback_days": lookback_days,
            "udan_target_inr": UDAN_TARGET_INR,
            "trunk_median_fare": round(trunk_median, 2) if trunk_median else None,
            "trunk_avg_fare": round(trunk_avg, 2),
            "breach_count": len(breaches),
            "breach_routes": breaches,
            "routes": reports,
            "policy_note": (
                "UDAN affordability monitoring supports MoCA's stated goal of affordable "
                "regional connectivity; flagging persistent breaches informs subsidy review."
            ),
        }

    @classmethod
    def _route_fares(
        cls,
        db: Session,
        route_id: int,
        observation_date: Optional[datetime.date],
        horizon_days: int,
        lookback_days: int,
    ) -> List[float]:
        query = db.query(FareObservation.base_fare).filter(
            FareObservation.route_id == route_id,
            FareObservation.advance_purchase_days == horizon_days,
            FareObservation.availability_status == "AVAILABLE",
            FareObservation.base_fare > 0,
        )
        if observation_date:
            window_start = observation_date - datetime.timedelta(days=lookback_days)
            query = query.filter(
                FareObservation.search_timestamp >= datetime.datetime.combine(window_start, datetime.time.min),
                FareObservation.search_timestamp
                <= datetime.datetime.combine(observation_date, datetime.time.max),
            )
        else:
            query = query.order_by(FareObservation.search_timestamp.desc()).limit(200)
        return [v for (v,) in query.all()]

    @classmethod
    def _latest_quote_date(
        cls,
        db: Session,
        route_id: int,
        observation_date: Optional[datetime.date],
        horizon_days: int,
    ) -> str:
        query = db.query(FareObservation.search_timestamp).filter(
            FareObservation.route_id == route_id,
            FareObservation.advance_purchase_days == horizon_days,
            FareObservation.availability_status == "AVAILABLE",
        )
        if observation_date:
            query = query.filter(
                FareObservation.search_timestamp
                <= datetime.datetime.combine(observation_date, datetime.time.max),
            )
        latest = query.order_by(FareObservation.search_timestamp.desc()).first()
        return latest[0].date().isoformat() if latest else None
