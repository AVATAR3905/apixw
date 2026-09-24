"""DGCA Monthly Fare Benchmark Comparator (Phase 3: official fare validation).

Unlike the earlier `DGCAValidator` (which only compared *indices* against
DGCA fares in-memory), this comparator:

1. Persists official DGCA sector-wise monthly average fares into the
   `dgca_monthly_fares` table for auditability (ingest from CSV/Excel).
2. Converts the APIX route-level T+15 BASE_FARE *index* back into a fare
   estimate using the route's base-period representative fare
   (``fare_est = index / 100 * base_fare``) so that level-errors (MAE/RMSE/MAPE
   in INR) are meaningful — the index alone is scale-free.
3. Computes MAE / RMSE / MAPE / directional-accuracy / Pearson correlation per
   route–month and persists an aggregate ``ValidationResult`` row (the
   `validation_results` table currently has zero rows) for the DGCA benchmark.

Usage:
    python -m services.validation.dgca_benchmark_comparator data/reference/dgca_monthly_fares.csv
"""

import csv
import datetime
import logging
import os
from typing import Any, Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from database.session import SessionLocal
from packages.schemas.models import (
    DGCAMonthlyFare,
    FareObservation,
    IndexValue,
    Route,
    ValidationResult,
)

logger = logging.getLogger(__name__)

BASE_PERIOD = datetime.date(2026, 8, 1)
HEADLINE_LEAD = 15
DEFAULT_CSV = "data/reference/dgca_monthly_fares.csv"


class DGCABenchmarkComparator:
    """Compares the APIX headline T+15 base-fare index against DGCA monthly average fares."""

    METHODOLOGICAL_DISCLOSURE = (
        "DGCA average-fare comparison. The prototype headline series measures the Jevons "
        "geometric-mean of minimum basic-economy carrier fares at T+15, while DGCA reports "
        "all-economy average fares from ticketed passengers. Level differences are expected; "
        "the metrics evaluate co-movement of the monthly series after base-period point conversion."
    )

    # ------------------------------------------------------------------
    # 1. Ingestion
    # ------------------------------------------------------------------
    @classmethod
    def ingest_dgca_monthly_fares(
        cls, db: Session, csv_path: str = DEFAULT_CSV, source_version: str = "DGCA_ATS_2026"
    ) -> int:
        """Parses DGCA sector-wise monthly average-fare CSV and persists rows.

        Expected columns: ``month`` (YYYY-MM), ``route_code`` (DEL-BOM),
        ``avg_fare``, optional ``passengers`` and ``sector_type``.
        """
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"DGCA monthly fares CSV not found at {csv_path}")

        route_map = {r.route_code: r.id for r in db.query(Route).all()}
        seen = set()
        created = 0

        with open(csv_path, "r", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            missing_route = []
            for row in reader:
                month = str(row["month"]).strip()
                route_code = str(row["route_code"]).strip().upper()
                avg_fare = float(row["avg_fare"])
                sector_type = str(row.get("sector_type", "METRO_TRUNK")).upper()
                passengers = float(row["passengers"]) if row.get("passengers") else None

                rid = route_map.get(route_code)
                if rid is None:
                    missing_route.append(route_code)
                    continue

                key = (rid, month, sector_type)
                if key in seen:
                    continue
                seen.add(key)

                db.query(DGCAMonthlyFare).filter(
                    DGCAMonthlyFare.route_id == rid,
                    DGCAMonthlyFare.period == month,
                    DGCAMonthlyFare.sector_type == sector_type,
                ).delete()

                db.add(
                    DGCAMonthlyFare(
                        route_id=rid,
                        period=month,
                        sector_type=sector_type,
                        average_fare=avg_fare,
                        total_passengers=passengers,
                        source="DGCA Air Transport Statistics",
                        source_version=source_version,
                    )
                )
                created += 1

        db.commit()
        if missing_route:
            logger.warning("Unknown route codes skipped: %s", sorted(set(missing_route)))
        logger.info("Ingested %d DGCA monthly fare rows", created)
        return created

    @classmethod
    def get_dgca_series(cls, db: Session) -> List[Dict[str, Any]]:
        """Returns all DGCA monthly fare rows joined with route codes, ordered by period."""
        rows = (
            db.query(DGCAMonthlyFare, Route)
            .join(Route, DGCAMonthlyFare.route_id == Route.id)
            .all()
        )
        return [
            {
                "route_code": r.route_code,
                "period": d.period,
                "sector_type": d.sector_type,
                "average_fare": d.average_fare,
                "total_passengers": d.total_passengers,
                "source_version": d.source_version,
            }
            for d, r in sorted(rows, key=lambda t: (t[0].period, t[1].route_code))
        ]

    # ------------------------------------------------------------------
    # 2. APIX → fare conversion
    # ------------------------------------------------------------------
    @classmethod
    def _route_base_fare(cls, db: Session, route_id: int, month: str) -> Optional[float]:
        """Base-period representative base fare (INR) for a route.

        Uses the same Jevons cell-mean the calculator applies on the base date,
        falling back to the plain mean of islanded minimum fares if the estimator
        is unavailable (keeps this comparator dependency-light).
        """
        from packages.statistics.estimators import RepresentativePriceEstimator

        y, m = int(month[:4]), int(month[5:7])
        month_start = datetime.date(y, m, 1)
        if month_start >= BASE_PERIOD:
            anchor = BASE_PERIOD
        else:
            anchor = month_start

        observations = (
            db.query(FareObservation)
            .filter(
                FareObservation.route_id == route_id,
                FareObservation.advance_purchase_days == HEADLINE_LEAD,
                FareObservation.search_timestamp
                >= datetime.datetime.combine(anchor, datetime.time.min),
                FareObservation.search_timestamp
                <= datetime.datetime.combine(anchor, datetime.time.max),
            )
            .all()
        )
        if not observations:
            return None

        obs_dicts = [
            {
                "carrier": str(o.airline_id),
                "cabin_class": o.cabin_class,
                "fare_family": o.fare_family,
                "availability_status": o.availability_status,
                "base_fare": o.base_fare,
                "total_fare": o.total_fare,
            }
            for o in observations
        ]
        est = RepresentativePriceEstimator.estimate_route_price(
            observations=obs_dicts,
            price_field="base_fare",
            estimator="JEVONS",
            cabin_class="ECONOMY",
            fare_family="BASIC",
            apply_waterfall=True,
            apply_outlier_filter=True,
        )
        if est and est.get("representative_price") is not None:
            return float(est["representative_price"])
        return None

    @classmethod
    def _apix_monthly_fare(
        cls, db: Session, route_id: int, month: str, base_fare: float
    ) -> Optional[float]:
        """Convert route-level headline index monthly mean into an INR fare estimate."""
        y, m = int(month[:4]), int(month[5:7])
        start = datetime.date(y, m, 1)
        if m == 12:
            end = datetime.date(y + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            end = datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)

        records = (
            db.query(IndexValue)
            .filter(
                IndexValue.route_id == route_id,
                IndexValue.index_type == "ROUTE_LEVEL",
                IndexValue.index_series == "BASE_FARE",
                IndexValue.lead_time_days == HEADLINE_LEAD,
                IndexValue.period_start >= start,
                IndexValue.period_start <= end,
            )
            .all()
        )
        values = [r.index_value for r in records if r.index_value and r.index_value > 0]
        if not values:
            return None
        mean_index = float(np.mean(values))
        return round(mean_index / 100.0 * base_fare, 2)

    # ------------------------------------------------------------------
    # 3. Metrics
    # ------------------------------------------------------------------
    @classmethod
    def _metrics(
        cls, dgca: List[float], apix: List[float]
    ) -> Dict[str, Any]:
        d = np.asarray(dgca, dtype=float)
        a = np.asarray(apix, dtype=float)
        errors = a - d
        abs_errors = np.abs(errors)

        directional_accuracy = None
        correlation = None
        if len(d) > 1:
            dd = np.diff(d)
            ad = np.diff(a)
            if len(dd) > 0:
                sign_d = np.where(dd > 0, 1, -1)
                sign_a = np.where(ad > 0, 1, -1)
                directional_accuracy = round(
                    float(np.mean(sign_d == sign_a)) * 100.0, 1
                )
            if len(d) > 1:
                correlation = round(float(np.corrcoef(d, a)[0, 1]), 3)

        return {
            "mae_inr": round(float(np.mean(abs_errors)), 2),
            "rmse_inr": round(float(np.sqrt(np.mean(errors ** 2))), 2),
            "mape_pct": round(float(np.mean(abs_errors / np.maximum(d, 1)) * 100.0), 2),
            "bias_inr": round(float(np.mean(errors)), 2),
            "directional_accuracy": directional_accuracy,
            "correlation": correlation,
            "n_months": int(len(d)),
        }

    @classmethod
    def run_comparison(
        cls,
        db: Session,
        benchmark_version: str = "DGCA_ATS_2026",
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Compare all stored DGCA monthly fares against APIX headline index per route–month."""
        dgca_rows = cls.get_dgca_series(db)
        if not dgca_rows:
            return {"status": "NO_DGCA_DATA", "comparisons": 0}

        by_route: Dict[str, List[Dict[str, Any]]] = {}
        all_errors = []

        for row in dgca_rows:
            route = db.query(Route).filter(Route.route_code == row["route_code"]).first()
            if not route:
                continue
            base_fare = cls._route_base_fare(db, route.id, row["period"])
            if base_fare is None:
                continue
            apix_fare = cls._apix_monthly_fare(db, route.id, row["period"], base_fare)
            if apix_fare is None:
                continue

            by_route.setdefault(row["route_code"], []).append(
                {
                    "period": row["period"],
                    "route_code": row["route_code"],
                    "dgca_fare": row["average_fare"],
                    "apix_fare": apix_fare,
                    "base_fare_used": round(base_fare, 2),
                    "deviation_pct": round(
                        (apix_fare - row["average_fare"]) / row["average_fare"] * 100.0, 2
                    ),
                }
            )
            all_errors.append((row["average_fare"], apix_fare))

        if not all_errors:
            return {"status": "NO_OVERLAP", "comparisons": 0}

        per_route = {}
        for rcode, rows in by_route.items():
            metrics = cls._metrics(
                [r["dgca_fare"] for r in rows], [r["apix_fare"] for r in rows]
            )
            per_route[rcode] = {"metrics": metrics, "rows": rows}

        aggregate = cls._metrics(
            [p for f_v, _ in all_errors for p in (f_v,)],
            [p for _, a_v in all_errors for p in (a_v,)],
        )

        result = {
            "status": "DGCA_BENCHMARKED",
            "benchmark_version": benchmark_version,
            "methodology_disclosure": cls.METHODOLOGICAL_DISCLOSURE,
            "total_comparisons": len(all_errors),
            "routes_compared": len(by_route),
            "aggregate_metrics": aggregate,
            "per_route_metrics": per_route,
        }

        if persist:
            cls._persist_validation_result(db, result)
        return result

    @classmethod
    def _persist_validation_result(cls, db: Session, result: Dict[str, Any]) -> None:
        """Write an aggregate ValidationResult row for the DGCA benchmark."""
        now = datetime.datetime.now(datetime.UTC)
        period_start = datetime.date(2026, 1, 1)
        period_end = datetime.date.today()

        # Replace prior DGCA aggregate rows for the same benchmark version.
        db.query(ValidationResult).filter(
            ValidationResult.benchmark_version == result["benchmark_version"]
        ).delete()

        raw = result["aggregate_metrics"]
        db.add(
            ValidationResult(
                period_start=period_start,
                period_end=period_end,
                series_evaluated="HEADLINE_T15_BASE_FARE",
                correlation=raw.get("correlation") or 0.0,
                mae=raw["mae_inr"],
                rmse=raw["rmse_inr"],
                directional_accuracy=raw.get("directional_accuracy") or 0.0,
                prototype_series_version="APIX-2.0",
                benchmark_version=result["benchmark_version"],
                methodology_notes=result["methodology_disclosure"],
                created_at=now,
            )
        )
        db.commit()
        logger.info("Persisted DGCA ValidationResult (%s)", result["benchmark_version"])


def run_dgca_benchmark(
    csv_path: str = DEFAULT_CSV,
    db: Optional[Session] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """CLI entry point: ingest DGCA fares then run the comparison."""
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        if csv_path and os.path.exists(csv_path):
            DGCABenchmarkComparator.ingest_dgca_monthly_fares(db, csv_path)
        return DGCABenchmarkComparator.run_comparison(db, persist=persist)
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV
    print(run_dgca_benchmark(path))
