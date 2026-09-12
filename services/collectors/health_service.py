"""Collector Health Telemetry & Operational Metrics Service (PRD Section 49, 52, 53)."""

import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import Source


class CollectorHealthService:
    """Tracks operational metrics, latency, success rates, and health classification for data sources."""

    # In-memory session metrics cache
    _metrics: Dict[int, Dict[str, Any]] = {}

    @classmethod
    def _get_or_init_metrics(cls, source_id: int) -> Dict[str, Any]:
        if source_id not in cls._metrics:
            cls._metrics[source_id] = {
                "jobs_total": 0,
                "jobs_success": 0,
                "jobs_failed": 0,
                "quotes_total": 0,
                "quotes_valid": 0,
                "quotes_rejected": 0,
                "parser_errors": 0,
                "schema_errors": 0,
                "latencies_ms": [],
                "last_successful_run": None,
            }
        return cls._metrics[source_id]

    @classmethod
    def record_run(
        cls,
        db: Session,
        source_id: int,
        success: bool,
        quotes_count: int = 0,
        valid_quotes_count: int = 0,
        latency_ms: float = 0.0,
        error_code: Optional[str] = None,
    ):
        """Records telemetry from a single collector execution."""
        m = cls._get_or_init_metrics(source_id)
        m["jobs_total"] += 1
        m["quotes_total"] += quotes_count
        m["quotes_valid"] += valid_quotes_count
        m["quotes_rejected"] += quotes_count - valid_quotes_count

        if latency_ms > 0:
            m["latencies_ms"].append(latency_ms)
            # Retain last 50 latency samples
            if len(m["latencies_ms"]) > 50:
                m["latencies_ms"].pop(0)

        now = datetime.datetime.now(datetime.UTC)
        if success:
            m["jobs_success"] += 1
            m["last_successful_run"] = now
        else:
            m["jobs_failed"] += 1
            if error_code == "PARSER_ERROR":
                m["parser_errors"] += 1
            elif error_code == "SCHEMA_CHANGED":
                m["schema_errors"] += 1

        # Evaluate and persist health status in Source record
        source = db.query(Source).filter(Source.id == source_id).first()
        if source and source.enabled and source.health_status not in ("DISABLED", "DOWN"):
            success_rate = (m["jobs_success"] / m["jobs_total"]) if m["jobs_total"] > 0 else 1.0
            if success_rate < 0.5:
                source.health_status = "DEGRADED"
            elif success_rate < 0.8:
                source.health_status = "WARNING"
            else:
                source.health_status = "HEALTHY"
            db.commit()

    @classmethod
    def get_source_health(cls, db: Session, source_id: int) -> Dict[str, Any]:
        """Returns comprehensive operational metrics for a specific source."""
        source = db.query(Source).filter(Source.id == source_id).first()
        if not source:
            raise ValueError(f"Source with ID {source_id} not found")

        m = cls._get_or_init_metrics(source_id)
        total_jobs = m["jobs_total"]
        success_rate = (
            round((m["jobs_success"] / total_jobs * 100.0), 1) if total_jobs > 0 else 100.0
        )
        valid_fare_rate = (
            round((m["quotes_valid"] / m["quotes_total"] * 100.0), 1)
            if m["quotes_total"] > 0
            else 100.0
        )
        avg_latency = (
            round(sum(m["latencies_ms"]) / len(m["latencies_ms"]), 1) if m["latencies_ms"] else 0.0
        )

        return {
            "source_id": source.id,
            "source_name": source.name,
            "source_type": source.type,
            "access_method": source.access_method,
            "permission_status": source.permission_status,
            "health_status": source.health_status,
            "enabled": source.enabled,
            "success_rate_pct": success_rate,
            "valid_fare_rate_pct": valid_fare_rate,
            "average_latency_ms": avg_latency,
            "jobs_total": total_jobs,
            "jobs_success": m["jobs_success"],
            "jobs_failed": m["jobs_failed"],
            "quotes_total": m["quotes_total"],
            "quotes_valid": m["quotes_valid"],
            "parser_errors": m["parser_errors"],
            "schema_errors": m["schema_errors"],
            "last_successful_run": m["last_successful_run"].isoformat()
            if m["last_successful_run"]
            else None,
        }

    @classmethod
    def get_all_sources_health(cls, db: Session) -> List[Dict[str, Any]]:
        """Returns health summaries for all registered sources."""
        sources = db.query(Source).all()
        return [cls.get_source_health(db, s.id) for s in sources]
