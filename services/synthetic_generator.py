"""Deterministic Synthetic Fare Observation Generator for Statistical Pipeline Verification."""

import datetime
import random
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database.session import SessionLocal
from packages.schemas.models import Airline, FareObservation, Route, Source
from packages.statistics.normalizer import FareNormalizer
from packages.statistics.quality import QualityEngine


class SyntheticFareGenerator:
    """Generates realistic, deterministic airfare observations for pipeline verification."""

    # Route baseline base fares (T+45 baseline in INR)
    ROUTE_BASELINES: Dict[str, float] = {
        "DEL-BOM": 3800.0,
        "DEL-BLR": 4100.0,
        "BOM-BLR": 3200.0,
        "DEL-CCU": 3900.0,
        "DEL-HYD": 3600.0,
        "BOM-MAA": 3400.0,
        "BLR-HYD": 2800.0,
        "DEL-MAA": 4200.0,
        # Regional / Thin routes (higher price level & volatility)
        "DEL-IXS": 5800.0,
        "DEL-DHM": 5200.0,
    }

    # Lead-time multiplier curve (T+45 to T+1)
    HORIZON_MULTIPLIERS: Dict[int, float] = {
        45: 1.00,  # Early-bird baseline
        30: 1.08,  # +8%
        15: 1.25,  # +25% (Headline Anchor)
        7: 1.60,  # +60%
        1: 2.45,  # +145% (Last-minute peak)
    }

    # Carrier pricing differentials relative to route baseline
    CARRIER_OFFSETS: Dict[str, float] = {
        "6E": 1.00,  # IndiGo benchmark
        "AI": 1.05,  # Air India full-service premium
        "SG": 0.94,  # SpiceJet budget discount
        "QP": 0.96,  # Akasa Air competitive
        "IX": 0.92,  # AI Express value
    }

    HORIZONS: List[int] = [1, 7, 15, 30, 45]

    @classmethod
    def generate_day_observations(
        cls,
        search_date: datetime.date,
        routes: List[Route],
        airlines: List[Airline],
        source_id: int,
        random_seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Generates observations for all routes and horizons for a single search date."""
        if random_seed is not None:
            random.seed(random_seed)

        observations: List[Dict[str, Any]] = []

        for route in routes:
            baseline = cls.ROUTE_BASELINES.get(route.route_code, 4000.0)

            for horizon in cls.HORIZONS:
                travel_date = search_date + datetime.timedelta(days=horizon)
                horizon_mult = cls.HORIZON_MULTIPLIERS.get(horizon, 1.0)

                # Each active carrier on route
                for airline in airlines:
                    # Regional routes typically have 2-3 carriers, metro routes have all 5
                    if route.corridor_type == "REGIONAL_THIN" and airline.code in ("SG", "IX"):
                        continue

                    carrier_mult = cls.CARRIER_OFFSETS.get(airline.code, 1.0)

                    # Simulate carrier schedule (1 to 3 flights per day)
                    flight_count = 3 if route.corridor_type == "METRO_TRUNK" else 1
                    min_flight_base_fare = float("inf")
                    flight_records = []

                    for f_idx in range(flight_count):
                        flight_num = f"{airline.code}-{100 + f_idx * 10 + route.id}"

                        # Check sold out probability (higher on T+1)
                        sold_out_prob = 0.12 if horizon == 1 else 0.02
                        is_sold_out = random.random() < sold_out_prob

                        if is_sold_out:
                            raw_record = {
                                "source_id": source_id,
                                "route_id": route.id,
                                "airline_id": airline.id,
                                "origin": route.origin_airport,
                                "destination": route.destination_airport,
                                "carrier": airline.code,
                                "flight_number": flight_num,
                                "search_timestamp": datetime.datetime.combine(
                                    search_date, datetime.time(9, 0)
                                ),
                                "travel_date": travel_date,
                                "advance_purchase_days": horizon,
                                "cabin_class": "ECONOMY",
                                "fare_family": "BASIC",
                                "availability_status": "SOLD_OUT",
                                "is_carrier_min_fare": False,
                                "is_synthetic": True,
                            }
                            normalized = FareNormalizer.normalize_observation(raw_record)
                            score, status, reason = QualityEngine.evaluate(normalized)
                            normalized.update(
                                {
                                    "source_id": source_id,
                                    "route_id": route.id,
                                    "airline_id": airline.id,
                                    "search_timestamp": raw_record["search_timestamp"],
                                    "travel_date": travel_date,
                                    "quality_score": score,
                                    "quality_status": status,
                                }
                            )
                            observations.append(normalized)
                            continue

                        # Daily slight natural price fluctuation (-4% to +6%)
                        noise = 1.0 + random.uniform(-0.04, 0.06)
                        base_fare = round(baseline * horizon_mult * carrier_mult * noise, 2)
                        if base_fare < min_flight_base_fare:
                            min_flight_base_fare = base_fare

                        # Components
                        fuel_surcharge = round(800.0 + random.uniform(0, 150), 2)
                        tax_amount = round((base_fare + fuel_surcharge) * 0.05, 2)  # 5% GST
                        udf = 350.0 if "DEL" in route.route_code else 250.0
                        convenience_fee = 299.0
                        total_fare = round(
                            base_fare + fuel_surcharge + tax_amount + udf + convenience_fee, 2
                        )

                        # Generate Economy Basic ticket
                        raw_basic = {
                            "source_id": source_id,
                            "route_id": route.id,
                            "airline_id": airline.id,
                            "origin": route.origin_airport,
                            "destination": route.destination_airport,
                            "carrier": airline.code,
                            "flight_number": flight_num,
                            "search_timestamp": datetime.datetime.combine(
                                search_date, datetime.time(9, 0)
                            ),
                            "travel_date": travel_date,
                            "advance_purchase_days": horizon,
                            "cabin_class": "ECONOMY",
                            "fare_family": "BASIC",
                            "availability_status": "AVAILABLE",
                            "base_fare": base_fare,
                            "fuel_surcharge": fuel_surcharge,
                            "tax_amount": tax_amount,
                            "development_fee": udf,
                            "convenience_fee": convenience_fee,
                            "other_fee": 0.0,
                            "total_fare": total_fare,
                            "is_synthetic": True,
                        }
                        flight_records.append(raw_basic)

                        # Also generate an Economy Flexi ticket (same flight, +60% base) to verify fare-mix protection!
                        flexi_base = round(base_fare * 1.6, 2)
                        flexi_tax = round((flexi_base + fuel_surcharge) * 0.05, 2)
                        flexi_total = round(
                            flexi_base + fuel_surcharge + flexi_tax + udf + convenience_fee, 2
                        )
                        raw_flexi = {
                            "source_id": source_id,
                            "route_id": route.id,
                            "airline_id": airline.id,
                            "origin": route.origin_airport,
                            "destination": route.destination_airport,
                            "carrier": airline.code,
                            "flight_number": flight_num,
                            "search_timestamp": datetime.datetime.combine(
                                search_date, datetime.time(9, 0)
                            ),
                            "travel_date": travel_date,
                            "advance_purchase_days": horizon,
                            "cabin_class": "ECONOMY",
                            "fare_family": "FLEXI",
                            "availability_status": "AVAILABLE",
                            "base_fare": flexi_base,
                            "fuel_surcharge": fuel_surcharge,
                            "tax_amount": flexi_tax,
                            "development_fee": udf,
                            "convenience_fee": convenience_fee,
                            "other_fee": 0.0,
                            "total_fare": flexi_total,
                            "is_carrier_min_fare": False,
                            "is_synthetic": True,
                        }
                        flight_records.append(raw_flexi)

                    # Tag the carrier minimum fare on basic economy
                    for rec in flight_records:
                        if (
                            rec["fare_family"] == "BASIC"
                            and rec["base_fare"] == min_flight_base_fare
                        ):
                            rec["is_carrier_min_fare"] = True
                        else:
                            rec["is_carrier_min_fare"] = False

                        normalized = FareNormalizer.normalize_observation(rec)
                        score, status, reason = QualityEngine.evaluate(normalized)
                        normalized.update(
                            {
                                "source_id": rec["source_id"],
                                "route_id": rec["route_id"],
                                "airline_id": rec["airline_id"],
                                "search_timestamp": rec["search_timestamp"],
                                "travel_date": rec["travel_date"],
                                "quality_score": score,
                                "quality_status": status,
                            }
                        )
                        observations.append(normalized)

        return observations

    @classmethod
    def seed_verification_dataset(
        cls,
        db: Session,
        days_count: int = 30,
        start_date: Optional[datetime.date] = None,
    ) -> int:
        """Populates database with 30 days of deterministic verification observations."""
        if start_date is None:
            start_date = datetime.date(2026, 8, 1)

        routes = db.query(Route).filter(Route.active).all()
        airlines = db.query(Airline).filter(Airline.active).all()
        source = (
            db.query(Source).filter(Source.name == "Synthetic Pipeline Verification Feed").first()
        )
        source_id = source.id if source else 1

        total_inserted = 0

        for day_offset in range(days_count):
            search_date = start_date + datetime.timedelta(days=day_offset)
            day_obs = cls.generate_day_observations(
                search_date=search_date,
                routes=routes,
                airlines=airlines,
                source_id=source_id,
                random_seed=42 + day_offset,
            )

            # Insert batch into database
            db_objs = [
                FareObservation(
                    source_id=o["source_id"],
                    route_id=o["route_id"],
                    airline_id=o["airline_id"],
                    search_timestamp=o["search_timestamp"],
                    travel_date=o["travel_date"],
                    advance_purchase_days=o["advance_purchase_days"],
                    flight_number=o["flight_number"],
                    cabin_class=o["cabin_class"],
                    fare_family=o["fare_family"],
                    stops=0,
                    availability_status=o["availability_status"],
                    is_carrier_min_fare=o.get("is_carrier_min_fare", False),
                    base_fare=o["base_fare"] if o["base_fare"] is not None else 0.0,
                    fuel_surcharge=o["fuel_surcharge"],
                    tax_amount=o["tax_amount"],
                    development_fee=o["development_fee"],
                    convenience_fee=o["convenience_fee"],
                    other_fee=o["other_fee"],
                    total_fare=o["total_fare"] if o["total_fare"] is not None else 0.0,
                    currency="INR",
                    is_synthetic=True,
                    extraction_method="SYNTHETIC",
                    quality_score=o["quality_score"],
                    quality_status=o["quality_status"],
                    collector_version="2.0.0",
                    schema_version="2.0.0",
                )
                for o in day_obs
            ]

            db.bulk_save_objects(db_objs)
            db.commit()
            total_inserted += len(db_objs)

        return total_inserted


if __name__ == "__main__":
    db = SessionLocal()
    try:
        count = SyntheticFareGenerator.seed_verification_dataset(db, days_count=30)
        print(
            f"Successfully generated and persisted {count} deterministic fare observations across 30 days."
        )
    finally:
        db.close()
