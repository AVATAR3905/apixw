"""Temporal Aggregation Engine for Weekly and Monthly Airfare Price Indices (PRD Section 28, 32)."""

import datetime
from typing import Any, Dict, List

import numpy as np
from scipy.stats import gmean


class TemporalAggregationEngine:
    """Computes multi-frequency aggregations (weekly and monthly) from daily high-frequency airfare series."""

    @classmethod
    def aggregate_weekly(cls, daily_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Computes weekly aggregated indices using geometric mean:
        Groups daily index records into ISO calendar weeks.
        """
        if not daily_records:
            return []

        # Group by (year, iso_week, series, index_type)
        grouped: Dict[tuple, List[Dict[str, Any]]] = {}
        for r in daily_records:
            dt = r["date"]
            if isinstance(dt, str):
                dt = datetime.date.fromisoformat(dt)
            iso_year, iso_week, _ = dt.isocalendar()
            series = r.get("index_series", "BASE_FARE")
            itype = r.get("index_type", "HEADLINE_T15")

            key = (iso_year, iso_week, series, itype)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r)

        weekly_results: List[Dict[str, Any]] = []
        for (year, week, series, itype), recs in sorted(grouped.items()):
            values = [
                float(r["index_value"])
                for r in recs
                if r.get("index_value") is not None and r["index_value"] > 0
            ]
            if not values:
                continue

            # Geometric mean of daily index values
            weekly_index = float(gmean(values))
            dates = [
                r["date"]
                if isinstance(r["date"], datetime.date)
                else datetime.date.fromisoformat(r["date"])
                for r in recs
            ]
            avg_coverage = float(np.mean([float(r.get("coverage_rate", 100.0)) for r in recs]))

            weekly_results.append(
                {
                    "period_type": "WEEKLY",
                    "period_label": f"{year}-W{week:02d}",
                    "period_start": min(dates).isoformat(),
                    "period_end": max(dates).isoformat(),
                    "index_series": series,
                    "index_type": itype,
                    "index_value": round(weekly_index, 2),
                    "coverage_rate": round(avg_coverage, 1),
                    "observation_days_count": len(values),
                }
            )

        return weekly_results

    @classmethod
    def aggregate_monthly(cls, daily_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Computes monthly aggregated indices suitable for comparison against MoSPI CPI:
        Calculates monthly calendar average of daily headline series.
        """
        if not daily_records:
            return []

        # Group by (year, month, series, index_type)
        grouped: Dict[tuple, List[Dict[str, Any]]] = {}
        for r in daily_records:
            dt = r["date"]
            if isinstance(dt, str):
                dt = datetime.date.fromisoformat(dt)
            series = r.get("index_series", "BASE_FARE")
            itype = r.get("index_type", "HEADLINE_T15")

            key = (dt.year, dt.month, series, itype)
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r)

        monthly_results: List[Dict[str, Any]] = []
        for (year, month, series, itype), recs in sorted(grouped.items()):
            values = [
                float(r["index_value"])
                for r in recs
                if r.get("index_value") is not None and r["index_value"] > 0
            ]
            if not values:
                continue

            # Arithmetic mean matching official NSO monthly index construction
            monthly_index = float(np.mean(values))
            dates = [
                r["date"]
                if isinstance(r["date"], datetime.date)
                else datetime.date.fromisoformat(r["date"])
                for r in recs
            ]
            avg_coverage = float(np.mean([float(r.get("coverage_rate", 100.0)) for r in recs]))

            monthly_results.append(
                {
                    "period_type": "MONTHLY",
                    "period_label": f"{year}-{month:02d}",
                    "period_start": min(dates).isoformat(),
                    "period_end": max(dates).isoformat(),
                    "index_series": series,
                    "index_type": itype,
                    "index_value": round(monthly_index, 2),
                    "coverage_rate": round(avg_coverage, 1),
                    "observation_days_count": len(values),
                }
            )

        return monthly_results
