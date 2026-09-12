"""Integration test verifying end-to-end collection framework execution."""

import datetime

from database.session import SessionLocal
from packages.schemas.models import CollectionJob, FareObservation, RawPayload, Route, Source
from services.collectors.health_service import CollectorHealthService
from services.collectors.mock_connector import MockConnector


def test_full_collection_job_pipeline():
    """
    Executes a collection job using MockConnector:
    1. Validates source eligibility.
    2. Executes fetch through CircuitBreaker.
    3. Persists raw payload with SHA-256 hash.
    4. Normalizes fare observations and scores quality.
    5. Emits telemetry metrics.
    """
    db = SessionLocal()
    try:
        # Create approved source
        source = Source(
            name="Mock Integration Source",
            type="OTA",
            access_method="MOCK",
            permission_status="APPROVED",
            health_status="ACTIVE",
            enabled=True,
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        route = db.query(Route).filter(Route.route_code == "DEL-BOM").first()
        assert route is not None

        # Create collection job
        job = CollectionJob(
            route_id=route.id,
            source_id=source.id,
            search_date=datetime.date(2026, 9, 1),
            travel_date=datetime.date(2026, 9, 16),
            advance_days=15,
            status="PENDING",
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        connector = MockConnector(source_id=source.id, source_name=source.name)
        result = connector.execute_job(db, job)

        assert result.success is True
        assert result.quotes_parsed == 2
        assert result.valid_quotes == 2
        assert result.raw_payload_id is not None

        # Verify DB records created
        db.refresh(job)
        assert job.status == "COMPLETED"

        raw_rec = db.query(RawPayload).filter(RawPayload.id == result.raw_payload_id).first()
        assert raw_rec is not None
        assert len(raw_rec.payload_hash) == 64

        obs_list = (
            db.query(FareObservation).filter(FareObservation.raw_payload_id == raw_rec.id).all()
        )
        assert len(obs_list) == 2
        assert obs_list[0].quality_status == "ACCEPT"

        # Verify telemetry
        health = CollectorHealthService.get_source_health(db, source.id)
        assert health["jobs_success"] >= 1
        assert health["quotes_valid"] >= 2
        assert health["health_status"] in ("ACTIVE", "HEALTHY")

    finally:
        db.query(FareObservation).filter(FareObservation.source_id == source.id).delete()
        db.query(RawPayload).filter(RawPayload.source_id == source.id).delete()
        db.query(CollectionJob).filter(CollectionJob.source_id == source.id).delete()
        db.query(Source).filter(Source.id == source.id).delete()
        db.commit()
        db.close()
