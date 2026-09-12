"""Automated Collection Scheduler for multi-route, multi-horizon search jobs (PRD Section 14, 39)."""

import datetime
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from database.session import SessionLocal
from packages.schemas.models import CollectionJob, Route, Source
from services.collectors.base import BaseConnector
from services.collectors.live_connector import LiveFlightConnector


class CollectionScheduler:
    """Orchestrates scheduled multi-horizon collection jobs across active domestic corridors."""

    HORIZONS = [1, 7, 15, 30, 45]

    def __init__(self, connector: Optional[BaseConnector] = None):
        self.connector = connector
        self.scheduler = BackgroundScheduler()
        self.is_running = False

    def trigger_collection_cycle(
        self,
        db: Session,
        search_date: Optional[datetime.date] = None,
        connector: Optional[BaseConnector] = None,
    ) -> Dict[str, Any]:
        """
        Executes a complete collection cycle:
        10 active routes x 5 horizons = 50 standardized collection jobs.
        """
        if search_date is None:
            search_date = datetime.date.today()

        active_connector = connector or self.connector
        if not active_connector:
            active_connector = LiveFlightConnector()

        routes = db.query(Route).filter(Route.active).all()
        source = db.query(Source).filter(Source.id == active_connector.source_id).first()
        source_id = source.id if source else active_connector.source_id

        jobs_created = 0
        jobs_success = 0
        jobs_failed = 0
        total_quotes = 0

        from services.collectors.dual_feed_runner import run_dual_feed_collection

        for route in routes:
            for horizon in self.HORIZONS:
                travel_date = search_date + datetime.timedelta(days=horizon)

                # Create Job Record
                job = CollectionJob(
                    route_id=route.id,
                    source_id=source_id,
                    search_date=search_date,
                    travel_date=travel_date,
                    advance_days=horizon,
                    status="PENDING",
                    attempt_count=1,
                    created_at=datetime.datetime.now(datetime.UTC),
                )
                db.add(job)
                db.commit()
                db.refresh(job)
                jobs_created += 1

                if connector is not None:
                    try:
                        res = active_connector.execute_job(db, job)
                        if res.success:
                            job.status = "COMPLETED"
                            job.collected_quotes_count = res.quotes_parsed
                            jobs_success += 1
                            total_quotes += res.quotes_parsed
                        else:
                            job.status = "FAILED"
                            jobs_failed += 1
                    except Exception as e:
                        job.status = "FAILED"
                        job.error_message = str(e)
                        jobs_failed += 1
                else:
                    # Production authentic dual-feed collection (Carrier Direct + Google Flights RPC Validator)
                    try:
                        reconciliation = run_dual_feed_collection(
                            route_code=route.route_code,
                            advance_days=horizon,
                            search_date=search_date,
                        )
                        count = len(reconciliation.get("primary_observations", []))
                        job.status = "COMPLETED"
                        job.collected_quotes_count = count
                        jobs_success += 1
                        total_quotes += count
                    except Exception as e:
                        # Resilient fallback to connector job execution
                        try:
                            res = active_connector.execute_job(db, job)
                            if res.success:
                                job.status = "COMPLETED"
                                jobs_success += 1
                                total_quotes += res.quotes_parsed
                            else:
                                job.status = "FAILED"
                                jobs_failed += 1
                        except Exception as inner_e:
                            job.status = "FAILED"
                            job.error_message = f"{e} | {inner_e}"
                            jobs_failed += 1
                db.commit()

        # Chain automated DailyIndexCalculatorService, CarrierInflationService, and VolatilityService
        from packages.statistics.carrier_inflation import CarrierInflationService
        from packages.statistics.volatility import VolatilityService
        from services.index_engine.calculator_service import DailyIndexCalculatorService

        computed_indices = []
        carrier_indices = []
        volatility_records = 0
        try:
            computed_indices = DailyIndexCalculatorService.calculate_day_indices(
                db=db,
                observation_date=search_date,
                methodology_version="APIX-2.0",
                weight_version="DGCA_2026_V1",
            )
        except Exception as e:
            print(f"[!] Warning: Automated post-collection index calculation error: {e}")

        try:
            carrier_indices = CarrierInflationService.calculate_carrier_indices(
                db=db,
                observation_date=search_date,
                horizon_days=15,
            )
        except Exception as e:
            print(
                f"[!] Warning: Automated post-collection carrier inflation calculation error: {e}"
            )

        try:
            for route in routes:
                res = VolatilityService.calculate_corridor_volatility(
                    db=db,
                    route_id=route.id,
                    calculation_date=search_date,
                    horizon_days=15,
                    save_to_db=True,
                )
                if res:
                    volatility_records += 1
        except Exception as e:
            print(f"[!] Warning: Automated post-collection volatility calculation error: {e}")

        return {
            "search_date": search_date.isoformat(),
            "jobs_total": jobs_created,
            "jobs_success": jobs_success,
            "jobs_failed": jobs_failed,
            "total_quotes_ingested": total_quotes,
            "indices_computed": len(computed_indices),
            "carrier_indices_computed": len(carrier_indices),
            "volatility_corridors_analyzed": volatility_records,
        }

    def start(self, cron_hour: int = 18, cron_minute: int = 0, multi_snapshot: bool = True):
        """Starts background APScheduler daily cron.

        If multi_snapshot=True, schedules snapshots at 06:00, 12:00, 18:00 (MoSPI anchor), and 23:00 IST.
        """
        if not self.is_running:
            if multi_snapshot:
                # 4 Daily Yield Snapshots
                for hour in [6, 12, 18, 23]:
                    self.scheduler.add_job(
                        func=self._cron_task,
                        trigger="cron",
                        hour=hour,
                        minute=0,
                        id=f"airfare_snapshot_{hour:02d}00",
                        replace_existing=True,
                    )
            else:
                self.scheduler.add_job(
                    func=self._cron_task,
                    trigger="cron",
                    hour=cron_hour,
                    minute=cron_minute,
                    id="daily_airfare_collection",
                    replace_existing=True,
                )
            self.scheduler.start()
            self.is_running = True

    def stop(self):
        """Shuts down scheduler gracefully."""
        if self.is_running:
            self.scheduler.shutdown(wait=False)
            self.is_running = False

    def _cron_task(self):
        """Internal worker called by cron schedule."""
        db = SessionLocal()
        try:
            self.trigger_collection_cycle(db)
        finally:
            db.close()
