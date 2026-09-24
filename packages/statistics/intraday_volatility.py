"""Intraday pricing volatility index (APIX-2.2 Governance Intelligence).

Airlines reprice multiple times per day.  The observatory's scheduler snapshots
the same departure dates at 06:00 / 12:00 / 18:00 / 23:00 IST, letting us derive:

* an **Intraday Volatility Index** — the coefficient of variation of the fares
  observed for the same travel date across collection windows, i.e. how much of
  a monthly average is noise vs signal; and
* a **best-time-to-book** signal — which collection window shows the lowest
  observed fares, by route.
"""

import datetime
import statistics
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import FareObservation, Route

WINDOWS = [
    ("MORNING_0600", 0, 8),
    ("NOON_1200", 8, 15),
    ("EVENING_1800", 15, 21),
    ("NIGHT_2300", 21, 24),
]


def _window_for(hour: int) -> str:
    for name, lo, hi in WINDOWS:
        if lo <= hour < hi:
            return name
    return "NIGHT_2300"


class IntradayVolatilityService:
    """Coefficient-of-variation by collection window and best-time-to-book signal."""

    @classmethod
    def get_route_intraday_volatility(
        cls,
        db: Session,
        route_code: str,
        observation_date: Optional[datetime.date] = None,
        travel_date: Optional[datetime.date] = None,
    ) -> Dict[str, Any]:
        route = db.query(Route).filter(Route.route_code == route_code).first()
        if not route:
            return {"error": f"Route {route_code} not found"}

        query = db.query(FareObservation).filter(
            FareObservation.route_id == route.id,
            FareObservation.availability_status == "AVAILABLE",
            FareObservation.base_fare > 0,
        )
        if observation_date:
            query = query.filter(
                FareObservation.search_timestamp
                >= datetime.datetime.combine(observation_date, datetime.time.min),
                FareObservation.search_timestamp
                <= datetime.datetime.combine(observation_date, datetime.time.max),
            )
        if travel_date:
            query = query.filter(FareObservation.travel_date == travel_date)

        rows = query.all()
        if not rows:
            return {"error": f"No observations for route {route_code}"}

        buckets: Dict[str, list] = {}
        for o in rows:
            bucket = _window_for(o.search_timestamp.hour)
            buckets.setdefault(bucket, []).append(o.base_fare)

        window_stats = []
        for name, lo, hi in WINDOWS:
            fares = buckets.get(name, [])
            if not fares:
                continue
            mean = statistics.mean(fares)
            window_stats.append(
                {
                    "window": name,
                    "window_hour": f"{lo:02d}:00",
                    "mean_fare": round(mean, 2),
                    "min_fare": round(min(fares), 2),
                    "max_fare": round(max(fares), 2),
                    "sample_count": len(fares),
                }
            )

        means = [w["mean_fare"] for w in window_stats]
        cv = (statistics.stdev(means) / statistics.mean(means)) if len(means) > 1 else 0.0
        best = min(window_stats, key=lambda w: w["mean_fare"]) if window_stats else None

        return {
            "route_code": route.route_code,
            "origin": route.origin,
            "destination": route.destination,
            "observation_date": (observation_date or datetime.date.today()).isoformat(),
            "travel_date": travel_date.isoformat() if travel_date else None,
            "intraday_volatility_cv": round(cv, 4),
            "intraday_volatility_pct": round(cv * 100.0, 2),
            "windows_observed": len(window_stats),
            "best_time_to_book": {
                "window": best["window"],
                "mean_fare": best["mean_fare"],
            }
            if best
            else None,
            "windows": window_stats,
        }

    @classmethod
    def get_network_intraday_summary(
        cls,
        db: Session,
        observation_date: Optional[datetime.date] = None,
    ) -> Dict[str, Any]:
        routes = db.query(Route).filter(Route.active).all()
        reports = []
        for route in routes:
            row = cls.get_route_intraday_volatility(
                db, route.route_code, observation_date=observation_date
            )
            if "error" not in row and row.get("windows_observed", 0) >= 1:
                reports.append(row)

        cvs = [r["intraday_volatility_cv"] for r in reports]
        avg_cv = statistics.mean(cvs) if cvs else 0.0
        best_to_book = min(reports, key=lambda r: r["best_time_to_book"]["mean_fare"]) if reports else None

        return {
            "status": "COMPLETED",
            "network_avg_intraday_volatility_pct": round(avg_cv * 100.0, 2),
            "windows_captured_per_route": [
                {"route_code": r["route_code"], "windows_observed": r["windows_observed"]}
                for r in reports
            ],
            "network_best_time_to_book": best_to_book["best_time_to_book"] if best_to_book else None,
            "routes": reports,
            "interpretation": (
                "Intraday CV measures how much of the monthly fare average is noise vs signal. "
                "High CV routes are repriced intra-day by airline yield management."
            ),
        }
