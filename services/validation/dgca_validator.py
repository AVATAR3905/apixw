"""DGCA Monthly Average Fare Validation & Backtesting Module.

Validates APIX index against DGCA published monthly average fares (from esankhyiki.mospi.gov.in).
Implements backtesting framework for 30+ days of historical comparison.
"""

import datetime
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from database.session import SessionLocal
from packages.schemas.models import IndexValue, Route

logger = logging.getLogger(__name__)


@dataclass
class DGCADataPoint:
    """Single DGCA monthly average fare data point."""
    month: str  # YYYY-MM
    route_code: str
    avg_fare: float
    passengers: int
    source: str = "DGCA_MONTHLY"


@dataclass
class ValidationMetrics:
    """Statistical validation metrics."""
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Squared Error
    mape: float  # Mean Absolute Percentage Error
    directional_accuracy: float  # % correct direction
    correlation: float  # Pearson correlation
    bias: float  # Mean error (positive = overestimation)
    n_samples: int


class DGCAValidator:
    """Validates APIX index against DGCA monthly average fares."""

    def __init__(self):
        self.dgca_data: List[DGCADataPoint] = []
        self.validation_results: List[Dict[str, Any]] = []

    def load_dgca_data(self, filepath: str) -> int:
        """Load DGCA monthly average fare data from CSV/Excel."""
        if not os.path.exists(filepath):
            logger.warning(f"DGCA data file not found: {filepath}")
            return 0

        try:
            if filepath.endswith(".csv"):
                df = pd.read_csv(filepath)
            elif filepath.endswith((".xlsx", ".xls")):
                df = pd.read_excel(filepath)
            else:
                raise ValueError("Unsupported file format. Use CSV or Excel.")

            # Expected columns: month, route_code, avg_fare, passengers
            required_cols = ["month", "route_code", "avg_fare"]
            for col in required_cols:
                if col not in df.columns:
                    raise ValueError(f"Missing required column: {col}")

            self.dgca_data = [
                DGCADataPoint(
                    month=str(row["month"]),
                    route_code=str(row["route_code"]).upper(),
                    avg_fare=float(row["avg_fare"]),
                    passengers=int(row.get("passengers", 0)),
                )
                for _, row in df.iterrows()
            ]

            logger.info(f"Loaded {len(self.dgca_data)} DGCA data points")
            return len(self.dgca_data)

        except Exception as e:
            logger.error(f"Failed to load DGCA data: {e}")
            return 0

    def load_dgca_from_esankhyiki(
        self,
        api_url: str = "https://esankhyiki.mospi.gov.in/api",
    ) -> int:
        """Fetch DGCA data from esankhyiki.mospi.gov.in API (placeholder)."""
        # This would implement actual API integration
        logger.info("DGCA API integration not yet implemented. Use load_dgca_data() with local file.")
        return 0

    def get_apix_monthly_avg(
        self,
        db: SessionLocal,
        route_code: str,
        year: int,
        month: int,
    ) -> Optional[float]:
        """Get APIX monthly average index value for a route."""
        start_date = datetime.date(year, month, 1)
        if month == 12:
            end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)

        # Get route
        route = db.query(Route).filter(Route.route_code == route_code.upper()).first()
        if not route:
            return None

        # Get daily index values for the month
        records = db.query(IndexValue).filter(
            IndexValue.route_id == route.id,
            IndexValue.index_type == "ROUTE_LEVEL",
            IndexValue.index_series == "BASE_FARE",
            IndexValue.period_start >= start_date,
            IndexValue.period_end <= end_date,
        ).order_by(IndexValue.period_start).all()

        if not records:
            return None

        values = [r.index_value for r in records if r.index_value > 0]
        return float(np.mean(values)) if values else None

    def compute_validation_metrics(
        self,
        dgca_values: List[float],
        apix_values: List[float],
    ) -> ValidationMetrics:
        """Compute statistical validation metrics."""
        if len(dgca_values) != len(apix_values) or len(dgca_values) == 0:
            return ValidationMetrics(0, 0, 0, 0, 0, 0, 0)

        dgca = np.array(dgca_values)
        apix = np.array(apix_values)

        # Absolute errors
        errors = apix - dgca
        abs_errors = np.abs(errors)

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(errors ** 2)))
        mape = float(np.mean(abs_errors / np.maximum(dgca, 1)) * 100)
        bias = float(np.mean(errors))

        # Directional accuracy (month-over-month direction)
        dgca_direction = np.diff(dgca)
        apix_direction = np.diff(apix)
        if len(dgca_direction) > 0:
            correct_direction = np.sum((dgca_direction > 0) == (apix_direction > 0))
            directional_accuracy = float(correct_direction / len(dgca_direction) * 100)
        else:
            directional_accuracy = 0.0

        # Pearson correlation
        if len(dgca) > 1:
            correlation = float(np.corrcoef(dgca, apix)[0, 1])
        else:
            correlation = 0.0

        return ValidationMetrics(
            mae=mae,
            rmse=rmse,
            mape=mape,
            directional_accuracy=directional_accuracy,
            correlation=correlation,
            bias=bias,
            n_samples=len(dgca_values),
        )

    def validate_monthly(
        self,
        db: SessionLocal,
        year: int,
        month: int,
    ) -> List[Dict[str, Any]]:
        """Validate APIX against DGCA for a specific month."""
        if not self.dgca_data:
            logger.warning("No DGCA data loaded")
            return []

        target_month = f"{year:04d}-{month:02d}"
        results = []

        for dgca_point in self.dgca_data:
            if dgca_point.month != target_month:
                continue

            apix_avg = self.get_apix_monthly_avg(db, dgca_point.route_code, year, month)
            if apix_avg is None:
                logger.warning(f"No APIX data for {dgca_point.route_code} in {target_month}")
                continue

            # Convert APIX index to fare estimate (using base period reference)
            # APIX index is relative to base (2026-08-01 = 100)
            # For validation, we compare relative changes or use route-level fares
            metrics = self.compute_validation_metrics(
                [dgca_point.avg_fare],
                [apix_avg],  # This needs proper fare conversion
            )

            result = {
                "month": target_month,
                "route_code": dgca_point.route_code,
                "dgca_avg_fare": dgca_point.avg_fare,
                "apix_index_value": apix_avg,
                "metrics": {
                    "mae": metrics.mae,
                    "rmse": metrics.rmse,
                    "mape": metrics.mape,
                    "directional_accuracy": metrics.directional_accuracy,
                    "correlation": metrics.correlation,
                    "bias": metrics.bias,
                },
            }
            results.append(result)
            self.validation_results.append(result)

        return results

    def validate_historical(
        self,
        db: SessionLocal,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
    ) -> Dict[str, Any]:
        """Run validation across historical period."""
        all_results = []
        current = datetime.date(start_year, start_month, 1)
        end = datetime.date(end_year, end_month, 1)

        while current <= end:
            results = self.validate_monthly(db, current.year, current.month)
            all_results.extend(results)

            # Next month
            if current.month == 12:
                current = datetime.date(current.year + 1, 1, 1)
            else:
                current = datetime.date(current.year, current.month + 1, 1)

        # Aggregate metrics
        if not all_results:
            return {"error": "No validation results"}

        # Aggregate across all routes and months
        all_mae = [r["metrics"]["mae"] for r in all_results]
        all_rmse = [r["metrics"]["rmse"] for r in all_results]
        all_mape = [r["metrics"]["mape"] for r in all_results]
        all_dir_acc = [r["metrics"]["directional_accuracy"] for r in all_results]
        all_corr = [r["metrics"]["correlation"] for r in all_results]
        all_bias = [r["metrics"]["bias"] for r in all_results]

        summary = {
            "period": f"{start_year}-{start_month:02d} to {end_year}-{end_month:02d}",
            "total_comparisons": len(all_results),
            "aggregate_metrics": {
                "mean_mae": float(np.mean(all_mae)),
                "mean_rmse": float(np.mean(all_rmse)),
                "mean_mape": float(np.mean(all_mape)),
                "mean_directional_accuracy": float(np.mean(all_dir_acc)),
                "mean_correlation": float(np.mean(all_corr)),
                "mean_bias": float(np.mean(all_bias)),
            },
            "per_route_metrics": self._aggregate_by_route(all_results),
            "detailed_results": all_results,
        }

        return summary

    def _aggregate_by_route(self, results: List[Dict]) -> Dict[str, Dict]:
        """Aggregate metrics by route."""
        by_route = {}
        for r in results:
            route = r["route_code"]
            if route not in by_route:
                by_route[route] = {"mae": [], "rmse": [], "mape": [], "dir_acc": [], "corr": []}
            by_route[route]["mae"].append(r["metrics"]["mae"])
            by_route[route]["rmse"].append(r["metrics"]["rmse"])
            by_route[route]["mape"].append(r["metrics"]["mape"])
            by_route[route]["dir_acc"].append(r["metrics"]["directional_accuracy"])
            by_route[route]["corr"].append(r["metrics"]["correlation"])

        return {
            route: {
                "mean_mae": float(np.mean(v["mae"])),
                "mean_rmse": float(np.mean(v["rmse"])),
                "mean_mape": float(np.mean(v["mape"])),
                "mean_directional_accuracy": float(np.mean(v["dir_acc"])),
                "mean_correlation": float(np.mean(v["corr"])),
                "n_months": len(v["mae"]),
            }
            for route, v in by_route.items()
        }

    def generate_validation_report(
        self,
        summary: Dict[str, Any],
        output_path: str,
    ) -> None:
        """Generate validation report as JSON/HTML."""
        import json

        with open(output_path, "w") as f:
            json.dump(summary, f, indent=2, default=str)

        logger.info(f"Validation report saved to {output_path}")

    def backtest_30_days(
        self,
        db: SessionLocal,
        end_date: Optional[datetime.date] = None,
    ) -> Dict[str, Any]:
        """Run 30-day backtest against DGCA data."""
        if end_date is None:
            end_date = datetime.date.today()

        start_date = end_date - datetime.timedelta(days=30)

        # Convert to year/month ranges
        start_year, start_month = start_date.year, start_date.month
        end_year, end_month = end_date.year, end_date.month

        return self.validate_historical(db, start_year, start_month, end_year, end_month)


def run_dgca_validation(
    dgca_data_path: str,
    db: Optional[SessionLocal] = None,
    output_dir: str = "validation_reports",
) -> Dict[str, Any]:
    """Main entry point for DGCA validation."""
    os.makedirs(output_dir, exist_ok=True)

    validator = DGCAValidator()
    loaded = validator.load_dgca_data(dgca_data_path)

    if loaded == 0:
        return {"error": "No DGCA data loaded"}

    if db is None:
        db = SessionLocal()

    try:
        # Run 30-day backtest
        summary = validator.backtest_30_days(db)

        # Save report
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"dgca_validation_{timestamp}.json")
        validator.generate_validation_report(summary, output_path)

        logger.info(f"DGCA validation complete: {output_path}")
        return summary

    finally:
        if db:
            db.close()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        result = run_dgca_validation(sys.argv[1])
        print(result)
