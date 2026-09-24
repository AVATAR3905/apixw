"""Automated Collection Scheduler for multi-route, multi-horizon search jobs (PRD Section 14, 39)."""

import datetime
from typing import Any, Dict, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from database.session import SessionLocal
from packages.schemas.models import CollectionJob, Route, Source
from packages.shared.time_utils import utcnow
from services.collectors.base import BaseConnector
from services.collectors.live_connector import LiveFlightConnector
from services.collectors.ota.easemytrip_scraper import EaseMyTripScraper
from services.collectors.ota.ixigo_scraper import IxigoScraper
from services.collectors.real_fare_normalizer import RealFareNormalizer


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

        # Resume support: a run that crashes partway (confirmed to happen --
        # an unhandled Node/Playwright-side crash can kill the whole process)
        # always restarted from route #1 with no memory of what it already
        # finished, so the same later routes in the fixed iteration order
        # were shortchanged every time. Two parts to fixing that:
        #
        # 1. Any job still PENDING from an earlier run of this same
        #    route/horizon/date/source never reached a terminal status --
        #    its owning process died before updating it -- so mark it FAILED
        #    (not retried in place; a fresh job below covers the retry) rather
        #    than leaving it as a permanent zombie that "trigger_collection_
        #    cycle does not abort on one job crashing" tests would otherwise
        #    keep finding.
        # 2. Skip creating a new job for any route/horizon that already has a
        #    COMPLETED job for this exact date/source -- so a resumed run
        #    fast-forwards past already-done work (a cheap DB query) straight
        #    to the point an earlier run actually stopped at, instead of
        #    re-scraping everything from DEL-BOM again.
        db.query(CollectionJob).filter(
            CollectionJob.search_date == search_date,
            CollectionJob.source_id == source_id,
            CollectionJob.status == "PENDING",
        ).update(
            {"status": "FAILED", "error_message": "Orphaned: owning process did not complete it"},
            synchronize_session=False,
        )
        db.commit()

        completed_today = {
            (row.route_id, row.advance_days)
            for row in db.query(CollectionJob.route_id, CollectionJob.advance_days).filter(
                CollectionJob.search_date == search_date,
                CollectionJob.source_id == source_id,
                CollectionJob.status == "COMPLETED",
            )
        }

        jobs_created = 0
        jobs_success = 0
        jobs_failed = 0
        jobs_skipped_already_done = 0
        total_quotes = 0

        from services.collectors.dual_feed_runner import run_dual_feed_collection

        for route in routes:
            for horizon in self.HORIZONS:
                if (route.id, horizon) in completed_today:
                    jobs_skipped_already_done += 1
                    continue

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
                    created_at=utcnow(),
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

                    # Real OTA collection (Ixigo, EaseMyTrip -- the two OTAs with
                    # a verified working live scrape path; the other four remain
                    # network/anti-bot blocked and are not attempted here).
                    # Production-only: gated the same way as the dual-feed call
                    # above (skipped when a test passes an explicit connector),
                    # so the test suite stays hermetic -- no real Playwright
                    # browser launches during `trigger_collection_cycle` tests.
                    for ota in (IxigoScraper(), EaseMyTripScraper()):
                        try:
                            ota_quotes = ota.scrape_corridor(
                                origin_airport=route.route_code.split("-")[0],
                                destination_airport=route.route_code.split("-")[1],
                                travel_date=travel_date,
                                advance_days=horizon,
                                db=db,
                            )
                            real_ota_quotes = [
                                q for q in ota_quotes if q.get("feed_type") == "OTA_AGGREGATOR"
                                and q.get("extraction_method") != "CALIBRATED_MODEL"
                            ]
                            if real_ota_quotes:
                                persisted = RealFareNormalizer.normalize_and_persist_observations(
                                    db=db,
                                    raw_quotes=real_ota_quotes,
                                    route_code=route.route_code,
                                    travel_date=travel_date,
                                    advance_days=horizon,
                                )
                                total_quotes += len(persisted)
                        except Exception as e:
                            print(
                                f"[!] Warning: {ota.source_name} OTA collection failed for "
                                f"{route.route_code} T+{horizon}: {e}"
                            )
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
            "jobs_skipped_already_done": jobs_skipped_already_done,
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
