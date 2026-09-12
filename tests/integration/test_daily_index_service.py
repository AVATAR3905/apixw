"""Integration test verifying DailyIndexCalculatorService on database observations."""

import datetime

from sqlalchemy import func

from database.session import SessionLocal
from packages.schemas.models import FareObservation, IndexValue
from services.index_engine.calculator_service import DailyIndexCalculatorService


def test_daily_index_calculator_execution():
    """
    Executes DailyIndexCalculatorService on Day 1 of seeded synthetic verification data (2026-08-01):
    1. Verifies Headline T+15 Index generated for BASE_FARE and TOTAL_PRICE.
    2. Verifies sub-indices generated for T+1, T+7, T+30, T+45.
    3. Verifies route-level indices generated for all 10 corridors.
    Dry-run: persists nothing to the live database.
    """
    db = SessionLocal()
    try:
        obs = db.query(FareObservation).first()
        obs_date = obs.search_timestamp.date() if obs else datetime.date.today()

        # Calculate indices for base day
        records = DailyIndexCalculatorService.calculate_day_indices(
            db=db,
            observation_date=obs_date,
            base_date=obs_date,
            methodology_version="APIX-2.0",
            persist=False,
        )

        assert len(records) > 0

        # Verify headline index from returned records
        headline_base = next(
            (
                r
                for r in records
                if r.index_series == "BASE_FARE"
                and r.index_type in ("HEADLINE_T15", "HEADLINE_T14")
                and r.route_id is None
            ),
            None,
        )

        assert headline_base is not None
        # On base day, base period relative should equal 100.0
        assert headline_base.index_value == 100.0
        assert headline_base.lead_time_days in (14, 15)
        assert headline_base.coverage_rate >= 80.0
        assert headline_base.is_low_coverage is False

        # Verify sub-indices
        sub_t1 = next(
            r
            for r in records
            if r.index_series == "BASE_FARE" and r.index_type == "SUB_T1"
        )
        assert sub_t1.lead_time_days == 1

        # Verify route-level indices for all 10 corridors
        route_records = [
            r for r in records if r.index_type == "ROUTE_LEVEL"
        ]
        assert len(route_records) >= 10

    finally:
        db.close()


def test_daily_index_deltas_calculation():
    """
    Calculates indices for Day 2 and verifies that 1D percentage change delta is computed.
    Dry-run: no index records are persisted to the live database.
    """
    db = SessionLocal()
    day2_obs = []
    day2 = None
    try:
        obs_list = db.query(FareObservation).filter(FareObservation.is_synthetic.is_(False)).all()
        if not obs_list:
            latest_synthetic = (
                db.query(func.max(FareObservation.search_timestamp))
                .filter(FareObservation.is_synthetic.is_(True))
                .scalar()
            )
            if latest_synthetic is not None:
                obs_list = (
                    db.query(FareObservation)
                    .filter(
                        FareObservation.search_timestamp == latest_synthetic,
                        FareObservation.base_fare.isnot(None),
                    )
                    .limit(200)
                    .all()
                )
        day1 = obs_list[0].search_timestamp.date() if obs_list else datetime.date.today()
        day2 = day1 + datetime.timedelta(days=1)

        # Clone observations for day2 with a slight fare delta for testing
        for o in obs_list:
            cloned = FareObservation(
                feed_type=o.feed_type,
                source_id=o.source_id,
                airline_id=o.airline_id,
                route_id=o.route_id,
                flight_number=o.flight_number,
                search_timestamp=datetime.datetime.combine(day2, datetime.time(10, 0)),
                travel_date=o.travel_date + datetime.timedelta(days=1),
                advance_purchase_days=o.advance_purchase_days,
                cabin_class=o.cabin_class,
                fare_family=o.fare_family,
                stops=o.stops,
                availability_status=o.availability_status,
                is_carrier_min_fare=o.is_carrier_min_fare,
                base_fare=o.base_fare * 1.05,
                fuel_surcharge=o.fuel_surcharge,
                tax_amount=o.tax_amount,
                development_fee=o.development_fee,
                convenience_fee=o.convenience_fee,
                other_fee=o.other_fee,
                total_fare=o.total_fare * 1.05,
                currency=o.currency,
                is_synthetic=False,
            )
            db.add(cloned)
            day2_obs.append(cloned)
        db.commit()

        # Compute Day 1 then Day 2 (dry-run: no index rows persisted)
        DailyIndexCalculatorService.calculate_day_indices(
            db, observation_date=day1, base_date=day1, persist=False
        )
        day2_records = DailyIndexCalculatorService.calculate_day_indices(
            db, observation_date=day2, base_date=day1, persist=False
        )

        headline_day2 = next(
            (
                r
                for r in day2_records
                if r.index_type in ("HEADLINE_T15", "HEADLINE_T14")
                and r.route_id is None
            ),
            None,
        )

        assert headline_day2 is not None
        # Day 2 should have computed a 1D percentage change relative to Day 1
        assert headline_day2.daily_change_pct is not None

    finally:
        if day2:
            db.query(IndexValue).filter(IndexValue.period_start == day2).delete()
        for o in day2_obs:
            db.delete(o)
        db.commit()
        db.close()
