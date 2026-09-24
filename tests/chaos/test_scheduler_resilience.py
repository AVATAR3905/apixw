"""Fault-injection tests for the collection scheduler's orchestration layer.

A production run is 10 routes x 5 horizons = 50 jobs, plus 3 independent
post-collection statistics passes (index, carrier-inflation, volatility).
One dead route or one crashing statistics pass must never take the other 49
jobs / 2 passes down with it -- this file locks that isolation in as a
regression contract (confirmed already correct; no bug fix needed here).
"""

import datetime
from unittest.mock import patch

from database.session import SessionLocal
from packages.schemas.models import CollectionJob, FareObservation, Route, Source
from packages.shared.time_utils import utcnow
from services.collectors.live_connector import LiveFlightConnector
from services.scheduler.collection_scheduler import CollectionScheduler


def _cleanup(db, cycle_date):
    db.query(FareObservation).filter(
        FareObservation.search_timestamp >= datetime.datetime.combine(cycle_date, datetime.time.min),
        FareObservation.search_timestamp <= datetime.datetime.combine(cycle_date, datetime.time.max),
    ).delete()
    db.query(CollectionJob).filter(CollectionJob.search_date == cycle_date).delete()
    db.commit()


def test_one_job_crashing_mid_cycle_does_not_abort_the_other_49():
    db = SessionLocal()
    cycle_date = datetime.date(2026, 9, 3)
    _cleanup(db, cycle_date)  # defensive: a prior run interrupted before its own
    # finally block (e.g. killed by a test-runner timeout) can leave stale
    # COMPLETED rows for this fixed date, which resume support would then
    # correctly skip, producing a false failure unrelated to any regression.
    try:
        source = db.query(Source).filter(
            Source.permission_status == "APPROVED", Source.enabled
        ).first()
        connector = LiveFlightConnector(source_id=source.id, source_name=source.name)
        original_execute = connector.execute_job
        call_count = {"n": 0}

        def flaky_execute_job(db, job):
            call_count["n"] += 1
            if call_count["n"] == 3:  # simulate a single job blowing up mid-cycle
                raise RuntimeError("simulated collector crash")
            return original_execute(db, job)

        connector.execute_job = flaky_execute_job
        scheduler = CollectionScheduler(connector=connector)

        summary = scheduler.trigger_collection_cycle(db, search_date=cycle_date, connector=connector)

        assert summary["jobs_total"] == 50
        assert summary["jobs_failed"] == 1
        assert summary["jobs_success"] == 49
        # The crashed job must be recorded as FAILED in the DB, not silently
        # dropped or left PENDING forever.
        jobs = db.query(CollectionJob).filter(CollectionJob.search_date == cycle_date).all()
        assert len(jobs) == 50
        assert sum(1 for j in jobs if j.status == "FAILED") == 1
        assert sum(1 for j in jobs if j.status == "COMPLETED") == 49
    finally:
        _cleanup(db, cycle_date)
        db.close()


def test_crashed_run_resumes_instead_of_restarting_from_scratch():
    """Regression coverage for a real gap found in production: a run that
    crashes partway always restarted from route #1 with no memory of what it
    already finished, so a fixed iteration order meant the *same* later
    routes were shortchanged every time a crash happened (confirmed: two
    consecutive real runs both crashed, and both times the routes after the
    crash point never got touched at all that day).

    Simulates the DB state left behind by an interrupted prior run -- some
    jobs COMPLETED, one left PENDING forever (the exact signature of a
    process that died mid-job) -- and verifies a fresh call: skips the
    already-COMPLETED work instead of re-collecting it, retries the orphaned
    PENDING job (marking it FAILED first, never left as a zombie), and still
    reaches every route/horizon that was never touched at all.
    """
    db = SessionLocal()
    cycle_date = datetime.date(2026, 9, 5)
    _cleanup(db, cycle_date)  # defensive: see comment on the T+3 test above.
    try:
        source = db.query(Source).filter(
            Source.permission_status == "APPROVED", Source.enabled
        ).first()
        routes = db.query(Route).filter(Route.active).all()
        assert len(routes) == 10

        # Simulate a prior run that got through the first 2 routes' full
        # horizon sets, then died mid-job on the 3rd route's first horizon.
        already_done_pairs = {(r.id, h) for r in routes[:2] for h in CollectionScheduler.HORIZONS}
        for route_id, horizon in already_done_pairs:
            db.add(CollectionJob(
                route_id=route_id, source_id=source.id, search_date=cycle_date,
                travel_date=cycle_date + datetime.timedelta(days=horizon),
                advance_days=horizon, status="COMPLETED", attempt_count=1,
                created_at=utcnow(),
            ))
        orphaned_route_id = routes[2].id
        db.add(CollectionJob(
            route_id=orphaned_route_id, source_id=source.id, search_date=cycle_date,
            travel_date=cycle_date + datetime.timedelta(days=1),
            advance_days=1, status="PENDING", attempt_count=1, created_at=utcnow(),
        ))
        db.commit()

        connector = LiveFlightConnector(source_id=source.id, source_name=source.name)
        scheduler = CollectionScheduler(connector=connector)
        summary = scheduler.trigger_collection_cycle(db, search_date=cycle_date, connector=connector)

        # 10 already-completed pairs skipped; the other 40 (including the
        # orphaned route's T+1, now retried) are freshly created and run.
        assert summary["jobs_skipped_already_done"] == 10
        assert summary["jobs_total"] == 40
        assert summary["jobs_success"] == 40

        jobs = db.query(CollectionJob).filter(CollectionJob.search_date == cycle_date).all()
        # 10 pre-existing COMPLETED (untouched) + 1 orphan marked FAILED (kept
        # as an audit trail, not deleted) + 40 freshly created and run.
        assert len(jobs) == 51
        # The orphaned PENDING job was marked FAILED (never left as a zombie)
        # and a separate fresh job for the same route/horizon completed it.
        orphan_route_jobs = [j for j in jobs if j.route_id == orphaned_route_id and j.advance_days == 1]
        assert len(orphan_route_jobs) == 2
        assert {j.status for j in orphan_route_jobs} == {"FAILED", "COMPLETED"}
        # Every other route/horizon reached a terminal COMPLETED status.
        assert all(j.status in ("COMPLETED", "FAILED") for j in jobs)
    finally:
        _cleanup(db, cycle_date)
        db.close()


def test_carrier_inflation_crash_does_not_stop_index_or_volatility_calc():
    db = SessionLocal()
    cycle_date = datetime.date(2026, 9, 4)
    _cleanup(db, cycle_date)  # defensive: see comment on the T+3 test above.
    try:
        source = db.query(Source).filter(
            Source.permission_status == "APPROVED", Source.enabled
        ).first()
        connector = LiveFlightConnector(source_id=source.id, source_name=source.name)
        scheduler = CollectionScheduler(connector=connector)

        with patch(
            "packages.statistics.carrier_inflation.CarrierInflationService.calculate_carrier_indices",
            side_effect=RuntimeError("simulated stats crash"),
        ):
            summary = scheduler.trigger_collection_cycle(
                db, search_date=cycle_date, connector=connector
            )

        # All 50 collection jobs still ran fine -- the crash is downstream.
        assert summary["jobs_success"] == 50
        # The crashed pass reports zero, but did not raise out of the cycle...
        assert summary["carrier_indices_computed"] == 0
        # ...and, critically, did not prevent the *other two* independent
        # statistics passes from completing.
        assert summary["indices_computed"] > 0
        assert summary["volatility_corridors_analyzed"] > 0
    finally:
        _cleanup(db, cycle_date)
        db.close()
