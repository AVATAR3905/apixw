"""Forecast backtesting: persist snapshots and score them against realized index values.

Forecasts are read-only estimates until their target dates pass. We store every
generated forecast in ``forecast_snapshots`` so that, once actual index values
arrive, the system can report how accurate each horizon actually was.
"""

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import ForecastSnapshot, IndexValue

logger = logging.getLogger(__name__)

HORIZON_BUCKETS = [(1, 7), (8, 14), (15, 21), (22, 28)]


@dataclass
class ForecastAccuracySummary:
    """Aggregate forecast accuracy metrics for one series/index_type."""
    series: str
    index_type: str
    snapshot_count: int = 0
    matched_count: int = 0
    available: bool = False
    mae: float = 0.0
    rmse: float = 0.0
    mape_pct: float = 0.0
    bias: float = 0.0
    p50_hit_rate_pct: float = 0.0
    p25_p75_coverage_pct: float = 0.0
    p10_p90_coverage_pct: float = 0.0
    by_horizon: List[Dict[str, Any]] = field(default_factory=list)
    recent: List[Dict[str, Any]] = field(default_factory=list)


def _json_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return None


def persist_forecast_snapshot(
    db: Session,
    series: str,
    index_type: str,
    forecast_date: Any,
    points: List[Any],
    ensemble_weights: Optional[Dict[str, float]] = None,
    model_versions: Optional[Dict[str, Any]] = None,
    history_days: Optional[int] = None,
    horizon_days: Optional[int] = None,
) -> None:
    """Persist one row per forecast day for later accuracy backtesting."""
    if not points:
        return
    horizon = horizon_days or len(points)
    snapshots = []
    for p in points:
        snapshots.append(
            ForecastSnapshot(
                series=series,
                index_type=index_type,
                forecast_date=forecast_date,
                target_date=p.target_date,
                horizon_days=p.horizon,
                p10=p.p10,
                p25=p.p25,
                p50=p.p50,
                p75=p.p75,
                p90=p.p90,
                model_confidence=p.model_confidence,
                ensemble_weights=_json_or_none(ensemble_weights),
                model_versions=_json_or_none(model_versions),
                history_days=history_days,
            )
        )
    db.add_all(snapshots)
    db.commit()
    logger.info(
        "Persisted %d forecast snapshots (series=%s type=%s horizon=%d)",
        len(snapshots),
        series,
        index_type,
        horizon,
    )


def _realized_values(
    db: Session, series: str, index_type: str
) -> Dict[str, float]:
    """Map realized index dates to actual values for a series/type."""
    rows = (
        db.query(IndexValue.period_start, IndexValue.index_value)
        .filter(
            IndexValue.index_series == series,
            IndexValue.index_type == index_type,
            IndexValue.route_id.is_(None),
        )
        .all()
    )
    return {r.period_start.isoformat(): r.index_value for r in rows}


def compute_forecast_accuracy(
    db: Session,
    series: str,
    index_type: str,
    lookback_days: int = 180,
) -> ForecastAccuracySummary:
    """Score persisted forecasts against realized index values.

    A snapshot 'matures' when its target date is equal to an observed index date
    (period_start). We compare the median forecast (P50) to the realized value and
    evaluate probabilistic coverage from the stored quantiles.
    """
    summary = ForecastAccuracySummary(series=series, index_type=index_type)
    realized = _realized_values(db, series, index_type)
    if not realized:
        return summary

    from datetime import datetime, timedelta

    cutoff = datetime.utcnow().date() - timedelta(days=lookback_days)
    snapshots = (
        db.query(ForecastSnapshot)
        .filter(
            ForecastSnapshot.series == series,
            ForecastSnapshot.index_type == index_type,
            ForecastSnapshot.generated_at >= cutoff,  # noqa
        )
        .order_by(ForecastSnapshot.generated_at.asc())
        .all()
    )
    summary.snapshot_count = len(snapshots)

    matched = []  # (horizon, actual, p10, p25, p50, p75, p90, confidence, generated_at)
    for snap in snapshots:
        actual = realized.get(snap.target_date.isoformat())
        if actual is None or snap.p50 is None:
            continue
        matched.append(
            {
                "target_date": snap.target_date.isoformat(),
                "generated_at": snap.generated_at.isoformat() if snap.generated_at else None,
                "horizon_days": snap.horizon_days,
                "actual": actual,
                "p10": snap.p10,
                "p25": snap.p25,
                "p50": snap.p50,
                "p75": snap.p75,
                "p90": snap.p90,
                "model_confidence": snap.model_confidence,
            }
        )

    if not matched:
        return summary

    summary.matched_count = len(matched)
    summary.available = True

    errors = [m["actual"] - m["p50"] for m in matched]
    abs_errors = [abs(e) for e in errors]
    relative_errors = [
        abs(e) / m["actual"] * 100.0 if m["actual"] else 0.0 for e, m in zip(errors, matched)
    ]
    summary.mae = sum(abs_errors) / len(abs_errors)
    summary.rmse = (sum(e * e for e in errors) / len(errors)) ** 0.5
    summary.mape_pct = sum(relative_errors) / len(relative_errors)
    summary.bias = sum(errors) / len(errors)

    def _hit(m, lo_key, hi_key):
        lo = m.get(lo_key)
        hi = m.get(hi_key)
        if lo is None or hi is None:
            return None
        return lo <= m["actual"] <= hi

    covered_50 = [h for h in (_hit(m, "p25", "p75") for m in matched) if h is not None]
    covered_80 = [h for h in (_hit(m, "p10", "p90") for m in matched) if h is not None]
    summary.p50_hit_rate_pct = (
        sum(covered_50) / len(covered_50) * 100.0 if covered_50 else 0.0
    )
    summary.p10_p90_coverage_pct = (
        sum(covered_80) / len(covered_80) * 100.0 if covered_80 else 0.0
    )
    summary.p25_p75_coverage_pct = summary.p50_hit_rate_pct

    # Per-horizon-bucket breakdown
    by_bucket: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for m in matched:
        bucket = "UNKNOWN"
        for lo, hi in HORIZON_BUCKETS:
            if lo <= m["horizon_days"] <= hi:
                bucket = f"{lo}-{hi}"
                break
        by_bucket[bucket].append(m)

    for bucket, items in by_bucket.items():
        bucket_errors = [it["actual"] - it["p50"] for it in items]
        bucket_abs = [abs(e) for e in bucket_errors]
        bucket_rel = [
            abs(e) / it["actual"] * 100.0 if it["actual"] else 0.0
            for e, it in zip(bucket_errors, items)
        ]
        summary.by_horizon.append(
            {
                "horizon_bucket": bucket,
                "count": len(items),
                "mae": sum(bucket_abs) / len(bucket_abs),
                "rmse": (sum(e * e for e in bucket_errors) / len(bucket_errors)) ** 0.5,
                "mape_pct": sum(bucket_rel) / len(bucket_rel),
                "bias": sum(bucket_errors) / len(bucket_errors),
            }
        )

    summary.recent = sorted(
        matched, key=lambda m: m["target_date"], reverse=True
    )[:50]

    return summary


def compute_all_accuracy(
    db: Session,
    series: Optional[str] = None,
    index_type: Optional[str] = None,
    lookback_days: int = 180,
) -> List[ForecastAccuracySummary]:
    """Compute accuracy summaries for all stored forecast series/types combinations."""
    query = db.query(ForecastSnapshot.series, ForecastSnapshot.index_type).distinct()
    combos = query.all()
    summaries = []
    for snap_series, snap_type in combos:
        if series and snap_series not in series.split(","):
            continue
        if index_type and snap_type not in index_type.split(","):
            continue
        summary = compute_forecast_accuracy(db, snap_series, snap_type, lookback_days)
        if summary.available:
            summaries.append(summary)
    return summaries
