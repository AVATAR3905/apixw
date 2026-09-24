"""Main Orchestrator: End-to-End Pipeline Execution.

Coordinates:
1. Carrier Direct Collection (4 airlines)
2. OTA Collection (6 OTAs)
3. Data Cleaning & Normalization
4. Index Calculation (Daily + Historical)
5. Forecasting (TimesFM + LightGBM + Statistical)
6. DGCA Validation
7. Cache Invalidation
8. Monitoring & Alerts
"""

import datetime
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import yaml

from database.session import SessionLocal
from packages.schemas.models import Route
from services.collectors.ota.multi_source_orchestrator import MultiSourceFlightOrchestrator
from services.index_engine.calculator_service import DailyIndexCalculatorService
from services.ml.ensemble import EnsembleForecaster, get_all_historical_data
from services.validation.dgca_validator import run_dgca_validation

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""
    stage: str
    success: bool
    records_processed: int
    errors: List[str]
    duration_seconds: float
    metadata: Dict[str, Any]


class APIXOrchestrator:
    """Main orchestrator for the APIX pipeline."""

    def __init__(self, config_path: str = "config/production.yaml"):
        self.config = self._load_config(config_path)
        self.results: List[PipelineResult] = []
        self.db: Optional[SessionLocal] = None

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        else:
            logger.warning(f"Config file not found: {config_path}, using defaults")
            return {}

    def _get_db(self) -> SessionLocal:
        """Get database session."""
        if self.db is None:
            self.db = SessionLocal()
        return self.db

    def close(self):
        """Close database connection."""
        if self.db:
            self.db.close()
            self.db = None

    def run_collection_pipeline(
        self,
        routes: Optional[List[str]] = None,
        advance_days: Optional[List[int]] = None,
        search_date: Optional[datetime.date] = None,
    ) -> PipelineResult:
        """Run data collection across all carriers and OTAs."""
        start_time = time.time()
        errors = []
        total_quotes = 0

        try:
            db = self._get_db()

            # Get active routes
            if routes is None:
                routes = [r.route_code for r in db.query(Route).filter(Route.active).all()]

            if advance_days is None:
                advance_days = self.config.get("collection", {}).get("carrier_direct", {}).get("advance_days", [1, 7, 15, 30, 45])

            if search_date is None:
                search_date = datetime.date.today()

            orchestrator = MultiSourceFlightOrchestrator()

            for route_code in routes:
                for adv_days in advance_days:
                    try:
                        logger.info(f"Collecting {route_code} T+{adv_days}...")
                        result = orchestrator.collect_corridor_all_sources(
                            route_code=route_code,
                            advance_days=adv_days,
                            search_date=search_date,
                            db=db,
                        )
                        collected = result.get("total_quotes_collected", 0)
                        total_quotes += collected
                        logger.info(f"  Collected {collected} quotes")
                    except Exception as e:
                        error_msg = f"Collection failed for {route_code} T+{adv_days}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)

            db.commit()

        except Exception as e:
            error_msg = f"Collection pipeline failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            if self.db:
                self.db.rollback()

        duration = time.time() - start_time
        return PipelineResult(
            stage="collection",
            success=len(errors) == 0,
            records_processed=total_quotes,
            errors=errors,
            duration_seconds=duration,
            metadata={"routes": routes, "advance_days": advance_days},
        )

    def run_index_calculation(
        self,
        observation_date: Optional[datetime.date] = None,
        base_date: Optional[datetime.date] = None,
        historical_range: Optional[Tuple[datetime.date, datetime.date]] = None,
    ) -> PipelineResult:
        """Run index calculation (daily or historical)."""
        start_time = time.time()
        errors = []
        records_created = 0

        try:
            db = self._get_db()

            if historical_range:
                # Historical recompute
                start_date, end_date = historical_range
                logger.info(f"Computing historical index range: {start_date} to {end_date}")
                records_created = DailyIndexCalculatorService.compute_historical_index_range(
                    db, start_date, end_date, persist=True
                )
                logger.info(f"Created {records_created} historical index records")
            else:
                # Daily calculation
                if observation_date is None:
                    observation_date = datetime.date.today()
                if base_date is None:
                    base_date = datetime.date(2026, 8, 1)

                logger.info(f"Calculating daily index for {observation_date} (base: {base_date})")
                records = DailyIndexCalculatorService.calculate_day_indices(
                    db=db,
                    observation_date=observation_date,
                    base_date=base_date,
                    persist=True,
                )
                records_created = len(records)
                logger.info(f"Created {records_created} daily index records")

            db.commit()

        except Exception as e:
            error_msg = f"Index calculation failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)
            if self.db:
                self.db.rollback()

        duration = time.time() - start_time
        return PipelineResult(
            stage="index_calculation",
            success=len(errors) == 0,
            records_processed=records_created,
            errors=errors,
            duration_seconds=duration,
            metadata={},
        )

    def run_forecasting(
        self,
        horizon: int = 28,
        history_days: int = 100,
    ) -> PipelineResult:
        """Run ensemble forecasting for all series."""
        start_time = time.time()
        errors = []
        forecasts_generated = 0

        try:
            db = self._get_db()

            # Get all historical data
            all_history = get_all_historical_data(db, history_days)

            # Filter to series/types with sufficient history
            filtered = {}
            for series, idx_types in all_history.items():
                filtered[series] = {}
                for idx_type, history in idx_types.items():
                    if len(history) >= 10:
                        filtered[series][idx_type] = history

            if not any(filtered.values()):
                raise ValueError("No series with sufficient historical data")

            # Generate forecasts
            forecaster = EnsembleForecaster()
            all_forecasts = forecaster.forecast_all_series(filtered, horizon)

            # Store forecasts (could persist to DB)
            for series, idx_types in all_forecasts.items():
                for idx_type, forecast in idx_types.items():
                    forecasts_generated += 1
                    logger.info(f"Forecast: {series}/{idx_type} - {len(forecast.points)} points")

        except Exception as e:
            error_msg = f"Forecasting failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        duration = time.time() - start_time
        return PipelineResult(
            stage="forecasting",
            success=len(errors) == 0,
            records_processed=forecasts_generated,
            errors=errors,
            duration_seconds=duration,
            metadata={},
        )

    def run_dgca_validation(
        self,
        dgca_data_path: str,
    ) -> PipelineResult:
        """Run DGCA validation/backtesting."""
        start_time = time.time()
        errors = []

        try:
            db = self._get_db()
            summary = run_dgca_validation(dgca_data_path, db)

            if "error" in summary:
                errors.append(summary["error"])

        except Exception as e:
            error_msg = f"DGCA validation failed: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        duration = time.time() - start_time
        return PipelineResult(
            stage="dgca_validation",
            success=len(errors) == 0,
            records_processed=0,
            errors=errors,
            duration_seconds=duration,
            metadata={},
        )

    def run_full_pipeline(
        self,
        mode: str = "daily",  # "daily", "historical", "full"
        **kwargs,
    ) -> Dict[str, Any]:
        """Run the complete APIX pipeline."""
        logger.info(f"Starting APIX pipeline in {mode} mode")

        self.results = []

        if mode in ("daily", "full"):
            # 1. Data Collection
            self.results.append(self.run_collection_pipeline(**kwargs))

            # 2. Index Calculation (daily)
            self.results.append(self.run_index_calculation(**kwargs))

            # 3. Forecasting
            self.results.append(self.run_forecasting(**kwargs))

        if mode in ("historical", "full"):
            # Historical recompute
            if "historical_range" in kwargs:
                self.results.append(self.run_index_calculation(historical_range=kwargs["historical_range"]))

        if mode in ("validation", "full"):
            # DGCA Validation
            if "dgca_data_path" in kwargs:
                self.results.append(self.run_dgca_validation(kwargs["dgca_data_path"]))

        # Summary
        total_duration = sum(r.duration_seconds for r in self.results)
        all_success = all(r.success for r in self.results)
        total_records = sum(r.records_processed for r in self.results)
        all_errors = [e for r in self.results for e in r.errors]

        summary = {
            "mode": mode,
            "success": all_success,
            "total_duration_seconds": total_duration,
            "total_records_processed": total_records,
            "stages": [
                {
                    "stage": r.stage,
                    "success": r.success,
                    "records": r.records_processed,
                    "duration": r.duration_seconds,
                    "errors": r.errors,
                }
                for r in self.results
            ],
            "total_errors": len(all_errors),
        }

        logger.info(f"Pipeline complete: success={all_success}, duration={total_duration:.1f}s, records={total_records}")
        return summary


def run_daily_pipeline(config_path: str = "config/production.yaml") -> Dict[str, Any]:
    """Entry point for daily pipeline execution."""
    orchestrator = APIXOrchestrator(config_path)
    try:
        return orchestrator.run_full_pipeline(mode="daily")
    finally:
        orchestrator.close()


def run_historical_recompute(
    start_date: datetime.date,
    end_date: datetime.date,
    config_path: str = "config/production.yaml",
) -> Dict[str, Any]:
    """Entry point for historical recomputation."""
    orchestrator = APIXOrchestrator(config_path)
    try:
        return orchestrator.run_full_pipeline(
            mode="historical",
            historical_range=(start_date, end_date),
        )
    finally:
        orchestrator.close()


def run_validation(
    dgca_data_path: str,
    config_path: str = "config/production.yaml",
) -> Dict[str, Any]:
    """Entry point for DGCA validation."""
    orchestrator = APIXOrchestrator(config_path)
    try:
        return orchestrator.run_full_pipeline(
            mode="validation",
            dgca_data_path=dgca_data_path,
        )
    finally:
        orchestrator.close()


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if len(sys.argv) < 2:
        print("Usage: python -m services.orchestrator [daily|historical|validation] [args...]")
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "daily":
        result = run_daily_pipeline()
        print(result)
    elif mode == "historical":
        if len(sys.argv) < 4:
            print("Usage: python -m services.orchestrator historical YYYY-MM-DD YYYY-MM-DD")
            sys.exit(1)
        start = datetime.date.fromisoformat(sys.argv[2])
        end = datetime.date.fromisoformat(sys.argv[3])
        result = run_historical_recompute(start, end)
        print(result)
    elif mode == "validation":
        if len(sys.argv) < 3:
            print("Usage: python -m services.orchestrator validation <dgca_data_path>")
            sys.exit(1)
        result = run_validation(sys.argv[2])
        print(result)
    else:
        print(f"Unknown mode: {mode}")
        sys.exit(1)
