"""Carrier market-concentration monitoring via Herfindahl-Hirschman Index (APIX-2.2).

Computes route-level HHI from observed carrier fare presence — a real-time proxy
for competition that complements DGCA's quarterly market-share reports and is
directly relevant to CCI competition monitoring.  Also correlates route-level HHI
with fare levels and volatility to surface concentration-pricing patterns.
"""

import datetime
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from packages.schemas.models import FareObservation, Route

HHI_MODERATE = 1500.0  # CCI / DOJ horizontal-merger guidepost
HHI_HIGH = 2500.0


def _share_vector(counts: List[int]) -> List[float]:
    total = float(sum(counts))
    if not total:
        return []
    return [c / total for c in counts]


def compute_hhi(share_vector: List[float], normalize=True) -> float:
    """HHI = sum(s_i^2), conventionally x10,000."""
    if not share_vector:
        return 0.0
    raw = sum(s**2 for s in share_vector)
    return round(raw * 10000.0, 1) if normalize else raw


class ConcentrationService:
    """Route-level Herfindahl-Hirschman index and concentration-fare correlation."""

    @classmethod
    def get_route_concentration(
        cls,
        db: Session,
        route_code: str,
        observation_date: Optional[datetime.date] = None,
        horizon_days: int = 15,
    ) -> Dict[str, Any]:
        route = db.query(Route).filter(Route.route_code == route_code).first()
        if not route:
            return {"error": f"Route {route_code} not found"}

        query = (
            db.query(FareObservation.airline_id, FareObservation.base_fare)
            .filter(
                FareObservation.route_id == route.id,
                FareObservation.advance_purchase_days == horizon_days,
                FareObservation.availability_status == "AVAILABLE",
                FareObservation.base_fare > 0,
            )
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

        from packages.schemas.models import Airline

        airline_names = {
            a.id: a.code for a in db.query(Airline).filter(Airline.id.in_({r[0] for r in rows})).all()
        }

        counts: Dict[int, int] = {}
        fares = []
        for airline_id, fare in rows:
            counts[airline_id] = counts.get(airline_id, 0) + 1
            fares.append(fare)

        shares = _share_vector(list(counts.values()))
        hhi = compute_hhi(shares)
        sorted_carriers = sorted(counts.items(), key=lambda kv: -kv[1])
        share_by_id = {cid: s for cid, s in zip(counts.keys(), shares)}

        return {
            "route_code": route.route_code,
            "origin": route.origin,
            "destination": route.destination,
            "corridor_type": route.corridor_type,
            "observation_date": (observation_date or datetime.date.today()).isoformat(),
            "horizon_days": horizon_days,
            "hhi": hhi,
            "hhi_band": cls._band(hhi),
            "carrier_count": len(counts),
            "carriers": [
                {
                    "carrier_code": airline_names.get(cid, str(cid)),
                    "quote_share_pct": round(share_by_id[cid] * 100.0, 1),
                }
                for cid, _ in sorted_carriers
            ],
            "mean_fare": round(float(np.mean(fares)), 2),
            "std_fare": round(float(np.std(fares)), 2),
        }

    @classmethod
    def get_network_concentration(
        cls,
        db: Session,
        observation_date: Optional[datetime.date] = None,
        horizon_days: int = 15,
    ) -> Dict[str, Any]:
        routes = db.query(Route).filter(Route.active).all()
        reports = []
        for route in routes:
            row = cls.get_route_concentration(
                db, route.route_code, observation_date, horizon_days
            )
            if "error" not in row:
                reports.append(row)

        reports.sort(key=lambda r: r["hhi"], reverse=True)

        if len(reports) >= 2:
            hhi_vals = np.array([r["hhi"] for r in reports])
            fare_vals = np.array([r["mean_fare"] for r in reports])
            std_vals = np.array([r["std_fare"] for r in reports])

            r_hhi_fare = np.corrcoef(hhi_vals, fare_vals)[0, 1]
            r_hhi_std = np.corrcoef(hhi_vals, std_vals)[0, 1]
        else:
            r_hhi_fare = r_hhi_std = None

        return {
            "status": "COMPLETED",
            "monitored_route_count": len(reports),
            "network_avg_hhi": round(float(np.mean([r["hhi"] for r in reports])), 1)
            if reports
            else 0.0,
            "high_concentration_routes": [
                r["route_code"]
                for r in reports
                if r["hhi_band"] == "HIGH"
            ],
            "moderate_concentration_routes": [
                r["route_code"]
                for r in reports
                if r["hhi_band"] == "MODERATE"
            ],
            "correlation_hhi_vs_fare": round(float(r_hhi_fare), 3) if r_hhi_fare is not None else None,
            "correlation_hhi_vs_volatility": round(float(r_hhi_std), 3) if r_hhi_std is not None else None,
            "routes": reports,
            "cci_relevance": (
                "Route-level HHI enables real-time monitoring of aviation market competition, "
                "complementing DGCA's quarterly market share reports."
            ),
        }

    @staticmethod
    def _band(hhi: float) -> str:
        if hhi >= HHI_HIGH:
            return "HIGH"
        if hhi >= HHI_MODERATE:
            return "MODERATE"
        return "LOW"
