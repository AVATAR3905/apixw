"""Price Fluctuation & Volatility Tracking Service.

Analyzes airfare volatility, intraday yield management swings, min-max price spreads,
standard deviations, price velocity, and automated surge alerts across monitored corridors.
"""

import datetime
import math
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import Airline, FareObservation, Route, RouteVolatilityRecord


class VolatilityService:
    """Computes corridor-level price dispersion, volatility indices, and surge classifications."""

    @classmethod
    def calculate_corridor_volatility(
        cls,
        db: Session,
        route_id: int,
        calculation_date: Optional[datetime.date] = None,
        horizon_days: int = 14,
        save_to_db: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Calculates volatility and price range spread for a single corridor.
        """
        query = db.query(FareObservation).filter(
            FareObservation.route_id == route_id,
            FareObservation.advance_purchase_days == horizon_days,
            FareObservation.cabin_class == "ECONOMY",
        )

        if calculation_date:
            query = query.filter(
                FareObservation.search_timestamp
                >= datetime.datetime.combine(calculation_date, datetime.time.min),
                FareObservation.search_timestamp
                <= datetime.datetime.combine(calculation_date, datetime.time.max),
            )

        observations = query.all()
        if not observations:
            return None

        fares = [o.base_fare for o in observations if o.base_fare and o.base_fare > 0]
        if not fares:
            return None

        n = len(fares)
        min_p = min(fares)
        max_p = max(fares)
        mean_p = sum(fares) / n

        sorted_fares = sorted(fares)
        mid = n // 2
        median_p = (
            sorted_fares[mid] if n % 2 != 0 else (sorted_fares[mid - 1] + sorted_fares[mid]) / 2.0
        )

        # Standard Deviation
        variance = sum((x - mean_p) ** 2 for x in fares) / (n - 1) if n > 1 else 0.0
        std_dev = math.sqrt(variance)

        # Spread percentage: (max - min) / mean * 100
        spread_pct = ((max_p - min_p) / mean_p * 100.0) if mean_p > 0 else 0.0

        # Status Classification
        if spread_pct < 4.0:
            status = "CALM"
        elif spread_pct <= 12.0:
            status = "MODERATE"
        elif spread_pct <= 22.0:
            status = "HIGH_VOLATILITY"
        else:
            status = "SURGE_ALERT"

        result = {
            "route_id": route_id,
            "calculation_date": (calculation_date or datetime.date.today()).isoformat(),
            "horizon_days": horizon_days,
            "min_price": round(min_p, 2),
            "max_price": round(max_p, 2),
            "mean_price": round(mean_p, 2),
            "median_price": round(median_p, 2),
            "spread_pct": round(spread_pct, 2),
            "std_dev": round(std_dev, 2),
            "volatility_status": status,
            "sample_size": n,
        }

        if save_to_db:
            calc_d = calculation_date or datetime.date.today()
            db.query(RouteVolatilityRecord).filter(
                RouteVolatilityRecord.route_id == route_id,
                RouteVolatilityRecord.calculation_date == calc_d,
                RouteVolatilityRecord.horizon_days == horizon_days,
            ).delete()

            record = RouteVolatilityRecord(
                route_id=route_id,
                calculation_date=calc_d,
                horizon_days=horizon_days,
                min_price=result["min_price"],
                max_price=result["max_price"],
                mean_price=result["mean_price"],
                median_price=result["median_price"],
                spread_pct=result["spread_pct"],
                std_dev=result["std_dev"],
                volatility_status=result["volatility_status"],
                sample_size=n,
            )
            db.add(record)
            db.commit()

        return result

    @classmethod
    def get_network_volatility_summary(
        cls,
        db: Session,
        calculation_date: Optional[datetime.date] = None,
        horizon_days: int = 14,
    ) -> Dict[str, Any]:
        """
        Retrieves volatility scorecard across all monitored domestic corridors.
        """
        routes = db.query(Route).filter(Route.active).all()
        corridor_reports = []

        for route in routes:
            vol = cls.calculate_corridor_volatility(
                db=db,
                route_id=route.id,
                calculation_date=calculation_date,
                horizon_days=horizon_days,
                save_to_db=False,
            )
            if vol:
                corridor_reports.append(
                    {
                        "route_code": route.route_code,
                        "origin": route.origin,
                        "destination": route.destination,
                        "corridor_type": route.corridor_type,
                        **vol,
                    }
                )

        # Sort corridors by volatility spread descending
        corridor_reports.sort(key=lambda x: x["spread_pct"], reverse=True)

        avg_spread = (
            sum(c["spread_pct"] for c in corridor_reports) / len(corridor_reports)
            if corridor_reports
            else 0.0
        )
        surge_routes = [
            c["route_code"]
            for c in corridor_reports
            if c["volatility_status"] in ("HIGH_VOLATILITY", "SURGE_ALERT")
        ]

        return {
            "monitored_corridors_count": len(corridor_reports),
            "average_network_spread_pct": round(avg_spread, 2),
            "active_surge_corridors_count": len(surge_routes),
            "surge_routes": surge_routes,
            "corridors": corridor_reports,
        }

    @classmethod
    def get_route_intraday_trajectory(
        cls,
        db: Session,
        route_code: str,
        observation_date: Optional[datetime.date] = None,
    ) -> Dict[str, Any]:
        """
        Retrieves flight-by-flight quotes for a corridor to visualize diurnal price distribution.
        """
        route = db.query(Route).filter(Route.route_code == route_code).first()
        if not route:
            return {"error": f"Route {route_code} not found"}

        query = (
            db.query(FareObservation, Airline)
            .join(Airline, FareObservation.airline_id == Airline.id)
            .filter(
                FareObservation.route_id == route.id,
                FareObservation.cabin_class == "ECONOMY",
            )
        )

        if observation_date:
            query = query.filter(
                FareObservation.search_timestamp
                >= datetime.datetime.combine(observation_date, datetime.time.min),
                FareObservation.search_timestamp
                <= datetime.datetime.combine(observation_date, datetime.time.max),
            )

        items = query.order_by(FareObservation.base_fare.asc()).all()

        quotes = []
        for obs, airline in items:
            quotes.append(
                {
                    "flight_number": obs.flight_number,
                    "carrier_code": airline.code,
                    "carrier_name": airline.name,
                    "base_fare": obs.base_fare,
                    "total_fare": obs.total_fare,
                    "advance_purchase_days": obs.advance_purchase_days,
                    "search_timestamp": obs.search_timestamp.isoformat(),
                    "fare_family": obs.fare_family,
                }
            )

        return {
            "route_code": route_code,
            "origin": route.origin,
            "destination": route.destination,
            "quotes_count": len(quotes),
            "quotes": quotes,
        }
