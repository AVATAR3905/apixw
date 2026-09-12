"""Unit tests for CarrierInflationService."""

import datetime

from sqlalchemy import func

from database.session import SessionLocal
from packages.schemas.models import FareObservation
from packages.statistics.carrier_inflation import CarrierInflationService


def test_carrier_inflation_calculation():
    """Verifies that carrier indices are calculated and persisted for active airlines."""
    db = SessionLocal()
    try:
        latest_synthetic = (
            db.query(func.max(FareObservation.search_timestamp))
            .filter(FareObservation.is_synthetic.is_(True))
            .scalar()
        )
        if latest_synthetic is not None:
            today = latest_synthetic.date()
        else:
            today = datetime.date(2026, 8, 1)

        records = CarrierInflationService.calculate_carrier_indices(
            db=db,
            observation_date=today,
            horizon_days=15,
        )

        assert len(records) > 0
        for r in records:
            assert r.carrier_code in ("6E", "AI", "SG", "QP", "IX")
            assert r.carrier_index_value > 0
            assert r.routes_covered >= 0

        # Verify scorecard
        scorecard = CarrierInflationService.get_latest_carrier_inflation(db, horizon_days=15)
        assert "carriers" in scorecard
        assert len(scorecard["carriers"]) == 4
        assert "carrier_inflation_spread" in scorecard
        assert scorecard["carrier_inflation_spread"] >= 0

    finally:
        db.close()


def test_carrier_timeseries_retrieval():
    """Verifies multi-carrier timeseries formatting."""
    db = SessionLocal()
    try:
        ts = CarrierInflationService.get_carrier_timeseries(db, horizon_days=15, limit=10)
        assert isinstance(ts, list)
        if ts:
            assert "date" in ts[0]
    finally:
        db.close()
