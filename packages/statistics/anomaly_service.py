"""Anomaly detection service: computes and persists per-point anomaly hits
from the historical index-value time series, with escalation classification.

Persists `AnomalyEvent` rows that can be surfaced by the `/analytics/anomalies`
endpoint.  Snapshot-replaces prior rows for the same observation_date+series
so repeated calls are idempotent.
"""

import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import AnomalyEvent, IndexValue
from packages.shared.time_utils import utcnow
from packages.statistics.anomaly_detector import (
    AnomalyHit,
    detect_on_values,
)


class PriceAnomalyService:
    """Scan the national headline index series for anomalous observation dates."""

    @classmethod
    def detect_latest(
        cls,
        db: Session,
        series: str = "BASE_FARE",
        series_type: str = "HEADLINE",
        index_type: str = "HEADLINE_T15",
        window_days: int = 28,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Detect anomalous index values in the trailing window and persist hits."""
        start = datetime.date.today() - datetime.timedelta(days=window_days)

        rows = (
            db.query(IndexValue)
            .filter(
                IndexValue.index_series == series,
                IndexValue.series_type == series_type,
                IndexValue.index_type == index_type,
                IndexValue.route_id.is_(None),
                IndexValue.period_start >= start,
            )
            .order_by(IndexValue.period_start.asc())
            .all()
        )
        if len(rows) < 4:
            return {"status": "INSUFFICIENT_DATA", "points_scanned": len(rows)}

        values = [r.index_value for r in rows]
        dates = [r.period_start for r in rows]
        report = detect_on_values(values, dates, series_name=f"{series} {series_type}")

        if persist and report.hits:
            cls._persist_hits(db, report.hits, series, series_type)

        return {
            "status": "COMPLETED",
            "series": series,
            "series_type": series_type,
            "index_type": index_type,
            "points_scanned": report.total_points,
            "reference_median": report.reference_median,
            "reference_mad": report.reference_mad,
            "hit_count": len(report.hits),
            "severity_counts": report.summary_counts,
            "hits": [
                {
                    "observation_date": h.observation_date.isoformat() if h.observation_date else None,
                    "value": h.value,
                    "z_score": h.z_score,
                    "severity": h.severity,
                    "anomaly_type": h.anomaly_type,
                }
                for h in report.hits
            ],
        }

    @classmethod
    def get_recent(
        cls,
        db: Session,
        days: int = 30,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Fetch recent persisted anomaly events."""
        start = datetime.date.today() - datetime.timedelta(days=days)
        query = db.query(AnomalyEvent).filter(AnomalyEvent.observation_date >= start)
        if status:
            query = query.filter(AnomalyEvent.status == status.upper())
        rows = query.order_by(AnomalyEvent.observation_date.desc()).limit(limit).all()
        return [
            {
                "id": r.id,
                "series": r.series,
                "series_type": r.series_type,
                "observation_date": r.observation_date.isoformat(),
                "anomaly_type": r.anomaly_type,
                "severity": r.severity,
                "z_score": r.z_score,
                "detected_value": r.detected_value,
                "reference_median": r.reference_median,
                "status": r.status,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
                "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
                "notes": r.notes,
            }
            for r in rows
        ]

    @classmethod
    def _persist_hits(
        cls,
        db: Session,
        hits: List[AnomalyHit],
        series: str,
        series_type: str,
    ) -> None:
        """Snapshot-replace prior events for each hit's observation_date + series."""
        for hit in hits:
            if not hit.observation_date:
                continue
            db.query(AnomalyEvent).filter(
                AnomalyEvent.observation_date == hit.observation_date,
                AnomalyEvent.series == series,
                AnomalyEvent.series_type == series_type,
                AnomalyEvent.route_id.is_(None),
            ).delete()
            db.add(
                AnomalyEvent(
                    series=series,
                    series_type=series_type,
                    observation_date=hit.observation_date,
                    anomaly_type=hit.anomaly_type,
                    severity=hit.severity,
                    z_score=hit.z_score,
                    reference_median=hit.reference_median,
                    detected_value=hit.value,
                    status="OPEN",
                    detected_at=utcnow(),
                )
            )
        db.commit()

    @classmethod
    def resolve_stale(cls, db: Session, max_age_days: int = 7) -> int:
        """Mark OPEN events older than max_age_days as RESOLVED."""
        cutoff = datetime.date.today() - datetime.timedelta(days=max_age_days)
        count = (
            db.query(AnomalyEvent)
            .filter(AnomalyEvent.status == "OPEN", AnomalyEvent.observation_date < cutoff)
            .update(
                {"status": "RESOLVED", "resolved_at": utcnow()},
                synchronize_session=False,
            )
        )
        db.commit()
        return count
