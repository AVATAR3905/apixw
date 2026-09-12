"""Unit tests for forecast snapshot persistence and backtest accuracy scoring."""

import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from packages.schemas.models import Base, ForecastSnapshot, IndexValue
from services.ml.forecast_accuracy import (
    compute_all_accuracy,
    compute_forecast_accuracy,
    persist_forecast_snapshot,
)


def _db_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)
    return TestingSession()


def _point(target_date, horizon, **kwargs):
    defaults = {
        "target_date": target_date,
        "horizon": horizon,
        "p10": 90.0,
        "p25": 97.0,
        "p50": 100.0,
        "p75": 103.0,
        "p90": 110.0,
        "model_confidence": 0.8,
        "component_forecasts": {},
    }
    defaults.update(kwargs)
    return type("P", (), defaults)()  # simple namespace object


def _seed_realized(db, series="BASE_FARE"):
    today = datetime.date(2026, 9, 10)
    for i in range(1, 29):
        d = today - datetime.timedelta(days=i)
        db.add(
            IndexValue(
                index_series=series,
                index_type="HEADLINE_T15",
                period_start=d,
                period_end=d,
                index_value=100.0 + i * 0.1,
                route_id=None,
            )
        )
    db.commit()


def test_persist_then_score_against_realized():
    db = _db_session()
    _seed_realized(db)

    forecast_date = datetime.date(2026, 9, 10)
    points = [_point(forecast_date - datetime.timedelta(days=h), horizon=h) for h in range(1, 4)]

    persist_forecast_snapshot(
        db,
        series="BASE_FARE",
        index_type="HEADLINE_T15",
        forecast_date=forecast_date,
        points=points,
        ensemble_weights={"timesfm": 0.5},
        model_versions={"timesfm": "2.5"},
        history_days=100,
        horizon_days=3,
    )

    assert db.query(ForecastSnapshot).count() == 3

    summary = compute_forecast_accuracy(db, "BASE_FARE", "HEADLINE_T15", lookback_days=180)
    assert summary.available is True
    assert summary.snapshot_count == 3
    assert summary.matched_count == 3
    # Forecast p50=100 vs realized ~100.x -> not huge errors
    assert summary.mae > 0
    assert summary.by_horizon, "expected a horizon-bucket breakdown"
    assert summary.recent
    db.close()


def test_no_matches_returns_unavailable():
    db = _db_session()
    # Store snapshots but no realized values exist
    persist_forecast_snapshot(
        db,
        series="TOTAL_PRICE",
        index_type="SUB_T7",
        forecast_date=datetime.date(2026, 9, 10),
        points=[_point(datetime.date(2026, 9, 15), horizon=5)],
    )
    summary = compute_forecast_accuracy(db, "TOTAL_PRICE", "SUB_T7", lookback_days=180)
    assert summary.available is False
    assert summary.matched_count == 0
    db.close()


def test_compute_all_accuracy_groups_combos():
    db = _db_session()
    _seed_realized(db)
    _seed_realized(db, series="TOTAL_PRICE")
    forecast_date = datetime.date(2026, 9, 10)
    points = [_point(forecast_date - datetime.timedelta(days=h), horizon=h) for h in range(1, 3)]

    persist_forecast_snapshot(
        db, "BASE_FARE", "HEADLINE_T15", forecast_date, points
    )
    persist_forecast_snapshot(
        db, "TOTAL_PRICE", "HEADLINE_T15", forecast_date, points
    )

    summaries = compute_all_accuracy(db, lookback_days=180)
    series_set = {s.series for s in summaries}
    assert "BASE_FARE" in series_set
    assert "TOTAL_PRICE" in series_set
    for s in summaries:
        assert s.available is True
    db.close()


def test_horizon_bucket_labels():
    db = _db_session()
    _seed_realized(db)
    forecast_date = datetime.date(2026, 9, 10)
    points = [_point(forecast_date - datetime.timedelta(days=h), horizon=h) for h in [1, 10, 20, 28]]
    persist_forecast_snapshot(db, "BASE_FARE", "HEADLINE_T15", forecast_date, points)

    summary = compute_forecast_accuracy(db, "BASE_FARE", "HEADLINE_T15", lookback_days=180)
    buckets = {b["horizon_bucket"] for b in summary.by_horizon}
    assert "1-7" in buckets
    assert "8-14" in buckets
    assert "15-21" in buckets
    assert "22-28" in buckets
    db.close()
