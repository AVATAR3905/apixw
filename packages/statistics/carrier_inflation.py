"""Carrier-Wise Price Inflation Service (CPI-Carrier).

Tracks and computes independent airline pricing behavior, Laspeyres carrier price indices,
pricing dispersion, and inflation trajectories across IndiGo, Air India, SpiceJet, and Akasa Air.
"""

import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import Airline, CarrierIndex, FareObservation, Route, RouteWeight
from packages.statistics.estimators import available_fares
from packages.statistics.weights import DGCAWeightEngine


class CarrierInflationService:
    """Calculates carrier-specific airfare inflation indices based on DGCA route weights."""

    CARRIER_NAMES = {
        "6E": "IndiGo",
        "AI": "Air India",
        "SG": "SpiceJet",
        "QP": "Akasa Air",
        "IX": "Air India Express",
    }

    @classmethod
    def get_carrier_route_prices(
        cls,
        db: Session,
        carrier_code: str,
        observation_date: datetime.date,
        advance_days: int = 14,
        price_field: str = "base_fare",
    ) -> Dict[str, float]:
        """
        Determines the lowest basic economy quote for a specific carrier on each route.
        """
        airline = db.query(Airline).filter(Airline.code == carrier_code).first()
        if not airline:
            return {}

        routes = db.query(Route).filter(Route.active).all()
        carrier_prices: Dict[str, float] = {}

        for route in routes:
            obs = (
                db.query(FareObservation)
                .filter(
                    FareObservation.route_id == route.id,
                    FareObservation.airline_id == airline.id,
                    FareObservation.search_timestamp
                    >= datetime.datetime.combine(observation_date, datetime.time.min),
                    FareObservation.search_timestamp
                    <= datetime.datetime.combine(observation_date, datetime.time.max),
                    FareObservation.advance_purchase_days == advance_days,
                    FareObservation.cabin_class == "ECONOMY",
                )
                .all()
            )

            if not obs:
                continue

            # Prefer BASIC fare family if present, otherwise lowest base fare
            basic_obs = [o for o in obs if o.fare_family == "BASIC"]
            target_obs = basic_obs if basic_obs else obs

            fares = available_fares(target_obs, price_field)
            if fares:
                carrier_prices[route.route_code] = min(fares)

        return carrier_prices

    @classmethod
    def calculate_carrier_indices(
        cls,
        db: Session,
        observation_date: datetime.date,
        base_date: Optional[datetime.date] = None,
        horizon_days: int = 14,
    ) -> List[CarrierIndex]:
        """
        Calculates and persists Laspeyres carrier indices for all active airlines.
        """
        if base_date is None:
            base_date = datetime.date(2026, 8, 1)

        raw_weights = DGCAWeightEngine.get_active_weights(db, target_date=observation_date)
        if not raw_weights:
            all_w = db.query(RouteWeight, Route).join(Route, RouteWeight.route_id == Route.id).all()
            raw_weights = {r.route_code: rw.weight for rw, r in all_w}

        airlines = db.query(Airline).all()
        created_records: List[CarrierIndex] = []

        for airline in airlines:
            carrier_code = airline.code

            # 1. Get carrier prices on observation date
            curr_prices = cls.get_carrier_route_prices(
                db=db,
                carrier_code=carrier_code,
                observation_date=observation_date,
                advance_days=horizon_days,
            )

            if not curr_prices:
                continue

            # 2. Get carrier prices on base date
            base_prices = cls.get_carrier_route_prices(
                db=db,
                carrier_code=carrier_code,
                observation_date=base_date,
                advance_days=horizon_days,
            )

            # Fallback if base date is missing or same
            for rcode, cp in curr_prices.items():
                if rcode not in base_prices or base_prices[rcode] <= 0:
                    base_prices[rcode] = cp

            # 3. Normalize DGCA weights across this carrier's active routes
            active_weights = {r: raw_weights.get(r, 0.1) for r in curr_prices if r in base_prices}
            total_carrier_weight = sum(active_weights.values())

            if total_carrier_weight <= 0:
                continue

            normalized_weights = {r: w / total_carrier_weight for r, w in active_weights.items()}

            # 4. Laspeyres calculation: I = sum(w_i * (P_t / P_0)) * 100
            index_value = (
                sum(
                    normalized_weights[r] * (curr_prices[r] / base_prices[r])
                    for r in normalized_weights
                )
                * 100.0
            )

            # 5. Compute historical percentage changes
            d1_pct = cls._compute_change(
                db, carrier_code, index_value, observation_date, days_back=1
            )
            d7_pct = cls._compute_change(
                db, carrier_code, index_value, observation_date, days_back=7
            )
            d30_pct = cls._compute_change(
                db, carrier_code, index_value, observation_date, days_back=30
            )

            # 6. Delete previous record for idempotency
            db.query(CarrierIndex).filter(
                CarrierIndex.carrier_code == carrier_code,
                CarrierIndex.period_date == observation_date,
                CarrierIndex.horizon_days == horizon_days,
            ).delete()

            carrier_idx = CarrierIndex(
                carrier_code=carrier_code,
                period_date=observation_date,
                horizon_days=horizon_days,
                carrier_index_value=round(index_value, 4),
                base_period_date=base_date,
                daily_change_pct=round(d1_pct, 2) if d1_pct is not None else None,
                weekly_change_pct=round(d7_pct, 2) if d7_pct is not None else None,
                monthly_change_pct=round(d30_pct, 2) if d30_pct is not None else None,
                routes_covered=len(curr_prices),
            )
            db.add(carrier_idx)
            created_records.append(carrier_idx)

        db.commit()
        return created_records

    @classmethod
    def _compute_change(
        cls,
        db: Session,
        carrier_code: str,
        current_val: float,
        current_date: datetime.date,
        days_back: int,
    ) -> Optional[float]:
        past_date = current_date - datetime.timedelta(days=days_back)
        past_record = (
            db.query(CarrierIndex)
            .filter(
                CarrierIndex.carrier_code == carrier_code,
                CarrierIndex.period_date <= past_date,
            )
            .order_by(CarrierIndex.period_date.desc())
            .first()
        )
        if past_record and past_record.carrier_index_value > 0:
            return (
                (current_val - past_record.carrier_index_value) / past_record.carrier_index_value
            ) * 100.0
        return None

    @classmethod
    def get_latest_carrier_inflation(cls, db: Session, horizon_days: int = 14) -> Dict[str, Any]:
        """
        Retrieves the latest carrier inflation scorecard, dispersion spreads, and rankings.
        """
        # Get latest distinct dates per carrier
        carriers = ["6E", "AI", "SG", "QP"]
        carrier_cards = []

        for code in carriers:
            record = (
                db.query(CarrierIndex)
                .filter(
                    CarrierIndex.carrier_code == code,
                    CarrierIndex.horizon_days == horizon_days,
                )
                .order_by(CarrierIndex.period_date.desc())
                .first()
            )

            name = cls.CARRIER_NAMES.get(code, code)
            if record:
                carrier_cards.append(
                    {
                        "carrier_code": code,
                        "carrier_name": name,
                        "index_value": round(record.carrier_index_value, 2),
                        "daily_change_pct": record.daily_change_pct or 0.0,
                        "weekly_change_pct": record.weekly_change_pct or 0.0,
                        "monthly_change_pct": record.monthly_change_pct or 0.0,
                        "routes_covered": record.routes_covered,
                        "period_date": record.period_date.isoformat(),
                    }
                )
            else:
                # If not yet calculated, return honest pending state
                carrier_cards.append(
                    {
                        "carrier_code": code,
                        "carrier_name": name,
                        "index_value": 100.0,
                        "daily_change_pct": 0.0,
                        "weekly_change_pct": 0.0,
                        "monthly_change_pct": 0.0,
                        "routes_covered": 0,
                        "period_date": datetime.date.today().isoformat(),
                    }
                )

        indices = [c["index_value"] for c in carrier_cards if c["routes_covered"] > 0]
        spread = (max(indices) - min(indices)) if len(indices) >= 2 else 0.0

        sorted_by_index = sorted(
            [c for c in carrier_cards if c["routes_covered"] > 0],
            key=lambda x: x["index_value"],
            reverse=True,
        )
        leader = sorted_by_index[0]["carrier_name"] if sorted_by_index else "N/A"
        value_airline = sorted_by_index[-1]["carrier_name"] if sorted_by_index else "N/A"

        return {
            "horizon": f"T+{horizon_days}",
            "carrier_inflation_spread": round(spread, 2),
            "inflation_leader": leader,
            "value_leader": value_airline,
            "carriers": carrier_cards,
        }

    @classmethod
    def get_carrier_timeseries(
        cls, db: Session, horizon_days: int = 14, limit: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Retrieves aligned multi-carrier timeseries data for comparative charting.
        """
        records = (
            db.query(CarrierIndex)
            .filter(CarrierIndex.horizon_days == horizon_days)
            .order_by(CarrierIndex.period_date.asc())
            .all()
        )

        dates_map: Dict[str, Dict[str, Any]] = {}
        for r in records:
            d_str = r.period_date.isoformat()
            if d_str not in dates_map:
                dates_map[d_str] = {"date": d_str}
            dates_map[d_str][r.carrier_code] = round(r.carrier_index_value, 2)

        return list(dates_map.values())[-limit:]
