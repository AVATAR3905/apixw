"""Integration test for CollectionScheduler executing full daily collection cycle."""

import datetime

from database.session import SessionLocal
from packages.schemas.models import CollectionJob, FareObservation, Source
from services.collectors.live_connector import LiveFlightConnector
from services.scheduler.collection_scheduler import CollectionScheduler


def test_collection_scheduler_full_cycle():
    """
    Verifies that trigger_collection_cycle executes jobs for:
    10 routes x 5 horizons = 50 collection jobs.
    """
    db = SessionLocal()
    try:
        # Use existing source #1 (Synthetic Pipeline Verification Feed) or create an approved test source
        source = (
            db.query(Source).filter(Source.permission_status == "APPROVED", Source.enabled).first()
        )
        assert source is not None

        connector = LiveFlightConnector(source_id=source.id, source_name=source.name)
        scheduler = CollectionScheduler(connector=connector)

        cycle_date = datetime.date(2026, 9, 2)
        summary = scheduler.trigger_collection_cycle(
            db, search_date=cycle_date, connector=connector
        )

        assert summary["jobs_total"] == 50  # 10 routes * 5 horizons
        assert summary["jobs_success"] == 50
        assert summary["jobs_failed"] == 0
        assert summary["total_quotes_ingested"] >= 200  # 50 jobs * 4 carriers

        # Verify collection jobs recorded in DB
        db_jobs = db.query(CollectionJob).filter(CollectionJob.search_date == cycle_date).all()
        assert len(db_jobs) == 50
        assert all(j.status == "COMPLETED" for j in db_jobs)

    finally:
        # Clean up test cycle records only (avoid deleting production observations)
        db.query(FareObservation).filter(
            FareObservation.search_timestamp
            >= datetime.datetime.combine(cycle_date, datetime.time.min),
            FareObservation.search_timestamp
            <= datetime.datetime.combine(cycle_date, datetime.time.max),
        ).delete()
        db.query(CollectionJob).filter(CollectionJob.search_date == cycle_date).delete()
        db.commit()
        db.close()
