"""Abstract Connector Interface and Base Collector Pipeline (PRD Section 13 & 14)."""

import datetime
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import CollectionJob, FareObservation, Route, Source
from packages.shared.time_utils import utcnow
from packages.statistics.normalizer import FareNormalizer
from packages.statistics.quality import QualityEngine
from services.collectors.circuit_breaker import (
    CollectorErrorCode,
    get_circuit_breaker,
)
from services.collectors.health_service import CollectorHealthService
from services.collectors.payload_store import PayloadStore
from services.collectors.source_registry import SourceRegistryService


@dataclass
class CollectionResult:
    """Standardized result returned after executing a collection job."""

    job_id: int
    success: bool
    quotes_parsed: int
    valid_quotes: int
    latency_ms: float
    raw_payload_id: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class BaseConnector(ABC):
    """Abstract base connector establishing contract for all live & mock data sources."""

    def __init__(self, source_id: int, source_name: str, rate_limit: int = 10):
        self.source_id = source_id
        self.source_name = source_name
        self.rate_limit = rate_limit
        self.circuit_breaker = get_circuit_breaker(source_id, source_name)

    @abstractmethod
    def fetch_route_horizon(
        self, route_code: str, search_date: datetime.date, advance_days: int
    ) -> Dict[str, Any]:
        """
        Executes query against external source and returns raw response payload.
        Expected format: {'status': 'OK', 'raw_body': ..., 'fares': [...]}
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Executes a lightweight ping/connectivity check against the source."""
        pass

    def execute_job(self, db: Session, job: CollectionJob) -> CollectionResult:
        """
        Executes a collection job through the compliance, resilience, and storage pipeline:
        1. Validates source eligibility (PRD Rule: unapproved sources cannot collect).
        2. Wraps fetch in CircuitBreaker with bounded retries.
        3. Persists raw response in immutable PayloadStore with SHA-256 hash.
        4. Normalizes fare components and assigns quality scores.
        5. Persists observations and records operational telemetry.
        """
        source = db.query(Source).filter(Source.id == self.source_id).first()
        if not source or not SourceRegistryService.can_collect(source):
            job.status = "FAILED"
            job.error_code = CollectorErrorCode.PERMISSION_DENIED.value
            job.error_message = (
                f"Source '{self.source_name}' is not approved or enabled for collection."
            )
            db.commit()
            return CollectionResult(
                job_id=job.id,
                success=False,
                quotes_parsed=0,
                valid_quotes=0,
                latency_ms=0.0,
                error_code=job.error_code,
                error_message=job.error_message,
            )

        route = db.query(Route).filter(Route.id == job.route_id).first()
        if not route:
            job.status = "FAILED"
            job.error_code = "ROUTE_NOT_FOUND"
            job.error_message = f"Route ID {job.route_id} not found."
            db.commit()
            return CollectionResult(
                job_id=job.id,
                success=False,
                quotes_parsed=0,
                valid_quotes=0,
                latency_ms=0.0,
                error_code=job.error_code,
            )

        job.status = "RUNNING"
        job.started_at = utcnow()
        db.commit()

        start_time = time.time()
        try:
            # Step 2: Fetch via circuit breaker
            raw_response = self.circuit_breaker.call(
                self.fetch_route_horizon,
                db=db,
                route_code=route.route_code,
                search_date=job.search_date,
                advance_days=job.advance_days,
            )

            latency_ms = round((time.time() - start_time) * 1000.0, 1)

            # Step 3: Store raw payload immutably
            raw_body = raw_response.get("raw_body", raw_response)
            payload_rec = PayloadStore.store_payload(
                db=db,
                source_id=self.source_id,
                content=raw_body,
                content_type="application/json",
                collection_job_id=job.id,
            )

            # Step 4: Parse & normalize observations
            parsed_raw_fares = raw_response.get("fares", [])
            valid_count = 0

            for f in parsed_raw_fares:
                f.update(
                    {
                        "source_id": self.source_id,
                        "route_id": route.id,
                        "origin": route.origin_airport,
                        "destination": route.destination_airport,
                        "advance_purchase_days": job.advance_days,
                    }
                )
                normalized = FareNormalizer.normalize_observation(f)
                score, status, _ = QualityEngine.evaluate(normalized)

                if status in ("ACCEPT", "ACCEPT_WITH_WARNING"):
                    valid_count += 1

                # Persist observation linked to raw payload
                db_obs = FareObservation(
                    source_id=self.source_id,
                    route_id=route.id,
                    airline_id=f.get("airline_id", 1),
                    search_timestamp=datetime.datetime.combine(
                        job.search_date, datetime.time(9, 0)
                    ),
                    travel_date=job.travel_date,
                    advance_purchase_days=job.advance_days,
                    flight_number=normalized["flight_number"],
                    cabin_class=normalized["cabin_class"],
                    fare_family=normalized["fare_family"],
                    stops=normalized.get("stops", 0),
                    availability_status=normalized["availability_status"],
                    is_carrier_min_fare=normalized.get("is_carrier_min_fare", False),
                    base_fare=normalized["base_fare"]
                    if normalized["base_fare"] is not None
                    else 0.0,
                    fuel_surcharge=normalized["fuel_surcharge"],
                    tax_amount=normalized["tax_amount"],
                    development_fee=normalized["development_fee"],
                    convenience_fee=normalized["convenience_fee"],
                    other_fee=normalized["other_fee"],
                    total_fare=normalized["total_fare"]
                    if normalized["total_fare"] is not None
                    else 0.0,
                    currency="INR",
                    is_synthetic=normalized.get("is_synthetic", False),
                    extraction_method=normalized.get("extraction_method")
                    or f.get("extraction_method")
                    or "NETWORK",
                    quality_score=score,
                    quality_status=status,
                    raw_payload_id=payload_rec.id,
                )
                db.add(db_obs)

            job.status = "COMPLETED"
            job.completed_at = utcnow()
            db.commit()

            # Step 5: Emit telemetry
            CollectorHealthService.record_run(
                db=db,
                source_id=self.source_id,
                success=True,
                quotes_count=len(parsed_raw_fares),
                valid_quotes_count=valid_count,
                latency_ms=latency_ms,
            )

            return CollectionResult(
                job_id=job.id,
                success=True,
                quotes_parsed=len(parsed_raw_fares),
                valid_quotes=valid_count,
                latency_ms=latency_ms,
                raw_payload_id=payload_rec.id,
            )

        except Exception as e:
            latency_ms = round((time.time() - start_time) * 1000.0, 1)
            err_code = getattr(e, "code", CollectorErrorCode.UNKNOWN.value)
            job.status = "FAILED"
            job.completed_at = utcnow()
            job.error_code = str(err_code)
            job.error_message = str(e)
            db.commit()

            CollectorHealthService.record_run(
                db=db,
                source_id=self.source_id,
                success=False,
                latency_ms=latency_ms,
                error_code=str(err_code),
            )

            return CollectionResult(
                job_id=job.id,
                success=False,
                quotes_parsed=0,
                valid_quotes=0,
                latency_ms=latency_ms,
                error_code=job.error_code,
                error_message=job.error_message,
            )
