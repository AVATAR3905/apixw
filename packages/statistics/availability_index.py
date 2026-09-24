"""Availability-Adjusted Index (APIX-2.2 Governance Intelligence).

A sold-out flight is not discarded data — it is a demand signal.  When inventory
on a route at a given travel date is SOLD_OUT on several carriers, the realized
fare consumers actually pay is higher than any quoted fare, because they are
forced onto later departures or higher fare classes.  The headline index
therefore *understates* true consumer cost during scarcity.

This module computes an availability adjustment factor per route and corrects
the headline index upward proportionally, using the observed SOLD_OUT pressure
as a scarcity proxy (academic airfare-economics practice, applied since 2018).
"""

import datetime
import math
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import FareObservation, Route

SCARCITY_BETA = 0.35  # saturation constant: max correction of +35% at full sell-out


def scarcity_premium_pct(sold_out_ratio: float, beta: float = SCARCITY_BETA) -> float:
    """Scarcity premium (%) implied by a SOLD_OUT quote ratio."""
    if sold_out_ratio <= 0.0:
        return 0.0
    return beta * min(sold_out_ratio, 1.0) * 100.0


class AvailabilityIndexService:
    """Scarcity-corrected index surface exposing sold-out pressure."""

    METHODOLOGY_DISCLOSURE = (
        "Availability-Adjusted Index: the observed SOLD_OUT ratio on a route/date "
        "(share of quotes with zero remaining inventory) is transformed into a scarcity "
        "premium via a saturating function (max +35% at full sell-out). This corrects the "
        "headline index for the consumer-cost understatement documented in academic "
        "airfare economics. The premium is a model parameter, not a quoted fare."
    )

    @classmethod
    def get_route_availability_adjusted(
        cls,
        db: Session,
        route_code: str,
        observation_date: Optional[datetime.date] = None,
        horizon_days: int = 15,
    ) -> Dict[str, Any]:
        route = db.query(Route).filter(Route.route_code == route_code).first()
        if not route:
            return {"error": f"Route {route_code} not found"}

        query = db.query(FareObservation).filter(
            FareObservation.route_id == route.id,
            FareObservation.advance_purchase_days == horizon_days,
            FareObservation.base_fare > 0,
        )
        if observation_date:
            query = query.filter(
                FareObservation.search_timestamp
                >= datetime.datetime.combine(observation_date, datetime.time.min),
                FareObservation.search_timestamp
                <= datetime.datetime.combine(observation_date, datetime.time.max),
            )

        rows = query.all()
        if not rows:
            return {"error": f"No observations for route {route_code}"}

        available = [o for o in rows if o.availability_status == "AVAILABLE"]
        sold_out_count = sum(1 for o in rows if o.availability_status == "SOLD_OUT")
        total = len(rows)
        sold_out_ratio = sold_out_count / total if total else 0.0

        if not available:
            return {
                "route_code": route.route_code,
                "error": "ALL_QUOTES_SOLD_OUT",
                "sold_out_ratio": round(sold_out_ratio, 3),
            }

        fares = [o.base_fare for o in available]
        confirmed_fare = math.exp(sum(math.log(f) for f in fares) / len(fares))

        premium_pct = scarcity_premium_pct(sold_out_ratio)
        adjusted_fare = confirmed_fare * (1.0 + premium_pct / 100.0)

        return {
            "route_code": route.route_code,
            "origin": route.origin,
            "destination": route.destination,
            "observation_date": (observation_date or datetime.date.today()).isoformat(),
            "horizon_days": horizon_days,
            "headline_fare": round(confirmed_fare, 2),
            "sold_out_ratio": round(sold_out_ratio, 3),
            "scarcity_premium_pct": round(premium_pct, 2),
            "availability_adjusted_fare": round(adjusted_fare, 2),
            "implied_adjustment_pct": round((adjusted_fare / confirmed_fare - 1) * 100.0, 2)
            if confirmed_fare
            else 0.0,
        }

    @classmethod
    def get_network_availability_adjusted(
        cls,
        db: Session,
        observation_date: Optional[datetime.date] = None,
        horizon_days: int = 15,
    ) -> Dict[str, Any]:
        routes = db.query(Route).filter(Route.active).all()
        reports = []
        for route in routes:
            row = cls.get_route_availability_adjusted(
                db, route.route_code, observation_date, horizon_days
            )
            if "error" not in row:
                reports.append(row)
            elif "error" in row and row.get("error") == "ALL_QUOTES_SOLD_OUT":
                reports.append(row)

        if not reports:
            return {
                "status": "NO_DATA",
                "methodology_disclosure": cls.METHODOLOGY_DISCLOSURE,
                "routes": [],
            }

        available_reports = [r for r in reports if "headline_fare" in r]
        if available_reports:
            headline = math.exp(
                sum(math.log(r["headline_fare"]) for r in available_reports) / len(available_reports)
            )
            adjusted = math.exp(
                sum(math.log(r["availability_adjusted_fare"]) for r in available_reports)
                / len(available_reports)
            )
            avg_premium = sum(r["scarcity_premium_pct"] for r in available_reports) / len(
                available_reports
            )
            avg_ratio = sum(r["sold_out_ratio"] for r in available_reports) / len(
                available_reports
            )
        else:
            headline = adjusted = avg_premium = avg_ratio = 0.0

        return {
            "status": "COMPLETED",
            "observation_date": (observation_date or datetime.date.today()).isoformat(),
            "horizon_days": horizon_days,
            "network_headline_fare": round(headline, 2),
            "network_availability_adjusted_fare": round(adjusted, 2),
            "network_scarcity_premium_pct": round(avg_premium, 2),
            "network_sold_out_ratio": round(avg_ratio, 3),
            "network_implied_adjustment_pct": round(
                (adjusted / headline - 1) * 100.0 if headline else 0.0, 2
            ),
            "methodology_disclosure": cls.METHODOLOGY_DISCLOSURE,
            "routes": reports,
            "interpretation": (
                "During high-demand periods the realized consumer cost exceeds any quoted "
                "fare because travellers are pushed to later departures or higher classes. "
                "The Availability-Adjusted Index corrects the headline for this scarcity effect."
            ),
        }
