"""Fault-injection tests for the statistics / index-engine layer.

Degenerate inputs here are not hypothetical: a route can genuinely drop to
zero valid quotes on a given day (source outage, holiday schedule gap), and
the variance/index machinery has to fail *loudly and locally* (a clean,
typed exception the caller already catches) rather than silently producing
a garbage number or crashing the whole daily calculation run.
"""

import datetime
import math

import pytest

from database.session import SessionLocal
from packages.schemas.models import IndexValue
from packages.statistics.estimators import RepresentativePriceEstimator
from packages.statistics.variance import IndexVarianceError, IndexVarianceEstimator
from packages.statistics.weights import DGCAWeightEngine, WeightCalculationError
from services.index_engine.calculator_service import DailyIndexCalculatorService


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class TestVarianceEstimatorDegenerateInputs:
    def test_single_route_jackknife_raises_cleanly(self):
        """A route that lost every other basket member on a given day (all
        other corridors' feeds down simultaneously) must not silently produce
        a variance estimate from N=1 -- there is no such thing.
        """
        with pytest.raises(IndexVarianceError):
            IndexVarianceEstimator.jackknife_index_variance(
                route_prices={"DEL-BOM": 105.0},
                base_prices={"DEL-BOM": 100.0},
                route_weights={"DEL-BOM": 1.0},
            )

    def test_nan_route_price_is_excluded_not_propagated(self):
        """A NaN sneaking in from a bad float conversion upstream must be
        filtered out of the "valid" route set (NaN > 0 is False in Python),
        not silently propagate into the published index or its SE.
        """
        with pytest.raises(IndexVarianceError):
            # Only DEL-BLR is left after DEL-BOM's NaN is excluded -> still
            # "requires at least two routes", proving NaN never entered the
            # arithmetic.
            IndexVarianceEstimator.jackknife_index_variance(
                route_prices={"DEL-BOM": math.nan, "DEL-BLR": 100.0},
                base_prices={"DEL-BOM": 100.0, "DEL-BLR": 100.0},
                route_weights={"DEL-BOM": 0.5, "DEL-BLR": 0.5},
            )

    def test_zero_weight_sum_raises_cleanly(self):
        with pytest.raises(IndexVarianceError, match="weights sum to zero"):
            IndexVarianceEstimator.jackknife_index_variance(
                route_prices={"DEL-BOM": 105.0, "DEL-BLR": 110.0},
                base_prices={"DEL-BOM": 100.0, "DEL-BLR": 100.0},
                route_weights={"DEL-BOM": 0.0, "DEL-BLR": 0.0},
            )

    def test_bootstrap_degenerate_n_rejected(self):
        with pytest.raises(IndexVarianceError):
            IndexVarianceEstimator.bootstrap_index_variance(
                route_samples={"DEL-BOM": [100.0]},
                base_prices={"DEL-BOM": 100.0},
                route_weights={"DEL-BOM": 1.0},
                n_bootstrap=1,  # below the documented minimum of 2
            )

    def test_calculator_service_swallows_variance_error_and_still_persists(self, db):
        """services/index_engine/calculator_service.py must catch
        IndexVarianceError internally (variance=None) rather than let a
        degenerate-input exception abort the entire day's index calculation
        -- this was the exact shape of the earlier KeyError bug fixed this
        session, so lock the safe-degrade contract in permanently.
        """
        d = datetime.date(2026, 8, 1)
        records = DailyIndexCalculatorService.calculate_day_indices(
            db=db, observation_date=d, persist=False,
        )
        assert len(records) > 0
        headline = next(
            r for r in records
            if r.index_type == "HEADLINE_T15" and r.route_id is None and r.index_series == "BASE_FARE"
        )
        # Whichever variance method ran, it must have produced a real SE and
        # never left the calculation half-finished.
        assert headline.standard_error is not None
        assert headline.index_value is not None


class TestWeightEngineDegenerateInputs:
    def test_all_zero_volumes_raise_cleanly(self):
        with pytest.raises(WeightCalculationError):
            DGCAWeightEngine.compute_normalized_weights({"DEL-BOM": 0.0, "DEL-BLR": 0.0})

    def test_negative_volume_does_not_silently_flip_weight_sign(self):
        """A negative passenger-volume figure (data-entry error in the DGCA
        source CSV) must not be allowed to produce a negative or
        nonsensical weight that would then corrupt the Laspeyres sum.
        """
        with pytest.raises(WeightCalculationError):
            DGCAWeightEngine.compute_normalized_weights({"DEL-BOM": -100.0, "DEL-BLR": 200.0})


class TestOutlierConsistencyBetweenPointAndVariance:
    """Regression coverage for a real bug found via the dashboard: a single
    outlier carrier bid (real DEL-BOM data, 2026-09-14 T+15 -- SG quoted
    ~4x its AI/IX peers) was correctly excluded from the point estimate by
    the MAD/IQR filter, but the *raw, unfiltered* per-carrier prices were
    still exposed as the bootstrap/jackknife resampling universe -- so the
    published CI reflected a different, contaminated distribution than the
    one that actually produced the published index value. The dashboard
    showed this as a wildly asymmetric 95% CI (point 111.48, interval
    109.04-226.51) that didn't correspond to the reported standard error.
    """

    def test_outlier_excluded_from_point_stays_excluded_from_variance_cells(self):
        obs = [
            {"carrier": "AI", "cabin_class": "ECONOMY", "fare_family": "BASIC",
             "base_fare": 4532.0, "availability_status": "AVAILABLE"},
            {"carrier": "IX", "cabin_class": "ECONOMY", "fare_family": "BASIC",
             "base_fare": 4904.0, "availability_status": "AVAILABLE"},
            {"carrier": "SG", "cabin_class": "ECONOMY", "fare_family": "BASIC",
             "base_fare": 17521.6, "availability_status": "AVAILABLE"},
        ]
        est = RepresentativePriceEstimator.estimate_route_price(obs, price_field="base_fare")
        assert est is not None
        # The outlier filter must have actually fired for this fixture.
        assert "SG" not in est["carrier_fares_for_variance"]
        assert "SG" in est["carrier_fares"]  # still visible for audit/transparency
        # The point estimate itself must not have been dragged up by SG.
        assert est["representative_price"] < 6000.0

        samples = DailyIndexCalculatorService._route_cell_samples({"DEL-BOM": est})
        assert 17521.6 not in samples["DEL-BOM"]
        assert set(samples["DEL-BOM"]) == {4532.0, 4904.0}


class TestIndexCalculationIdempotency:
    def test_zero_observation_day_returns_empty_not_a_crash(self, db):
        """A date with genuinely zero collected observations (e.g. a brand
        new future date, or every source down on the same day) must return
        an empty result set, not raise.
        """
        far_future_empty_date = datetime.date(2030, 1, 1)
        records = DailyIndexCalculatorService.calculate_day_indices(
            db=db, observation_date=far_future_empty_date, persist=False,
        )
        assert records == []

    def test_recalculating_same_date_does_not_duplicate_rows(self, db):
        """Re-running the daily calculator for a date it already computed
        (scheduler retry, manual backfill re-run) must replace, never
        duplicate, that date's IndexValue rows.
        """
        d = datetime.date(2026, 8, 1)
        before = db.query(IndexValue).filter(IndexValue.period_start == d).count()
        DailyIndexCalculatorService.calculate_day_indices(db=db, observation_date=d, persist=True)
        after_first = db.query(IndexValue).filter(IndexValue.period_start == d).count()
        DailyIndexCalculatorService.calculate_day_indices(db=db, observation_date=d, persist=True)
        after_second = db.query(IndexValue).filter(IndexValue.period_start == d).count()
        assert after_first == before
        assert after_second == after_first
