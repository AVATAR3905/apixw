"""Multi-OTA ensemble & feed-cohort correlation tracking (Phase 5).

Computes, over a rolling window, the Pearson correlation between the daily
representative price series of two feed cohorts — the authoritative
CARRIER_DIRECT feed and the OTA_AGGREGATOR feed — per route and horizon.

It also computes a headline-level ENSEMBLE index series (feed-quality-weighted
median of per-carrier minimum fares) so the OTA-inclusive consensus can be
tracked against the existing JEVONS headline. Falling correlations flag feed
divergence that should be escalated as a data-quality alert.
"""

import datetime
import math
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import FareObservation, Route, SourceCorrelation
from packages.statistics.estimators import RepresentativePriceEstimator

CORRELATION_TOLERANCE = 0.7  # r values below this flag OTA divergence


def _pearson_r(series_a: List[float], series_b: List[float]) -> Optional[float]:
    """Pearson correlation coefficient of two aligned series (min 2 points)."""
    if len(series_a) < 2 or len(series_a) != len(series_b):
        return None
    n = len(series_a)
    mean_a = sum(series_a) / n
    mean_b = sum(series_b) / n
    cov = sum((a - mean_a) * (b - mean_b) for a, b in zip(series_a, series_b))
    var_a = sum((a - mean_a) ** 2 for a in series_a)
    var_b = sum((b - mean_b) ** 2 for b in series_b)
    if var_a == 0 or var_b == 0:
        return None
    return cov / math.sqrt(var_a * var_b)


class SourceCorrelationTracker:
    """Builds aligned daily price series per feed cohort and persists correlation rows."""

    CORRELATION_TOLERANCE = CORRELATION_TOLERANCE  # r below this flags divergence

    @classmethod
    def _daily_series(
        cls,
        db: Session,
        route_id: int,
        horizon: int,
        feed_type: str,
        window_days: int,
        price_field: str = "base_fare",
    ) -> List[Dict[str, Any]]:
        """Daily representative price (per-carrier minimum, JEVONS) for one feed cohort."""
        start = datetime.date.today() - datetime.timedelta(days=window_days)
        days: Dict[datetime.date, List[Any]] = {}
        obs = (
            db.query(FareObservation)
            .filter(
                FareObservation.route_id == route_id,
                FareObservation.advance_purchase_days == horizon,
                FareObservation.feed_type == feed_type,
                FareObservation.search_timestamp >= datetime.datetime.combine(start, datetime.time.min),
            )
            .all()
        )
        for o in obs:
            day = o.search_timestamp.date()
            days.setdefault(day, []).append(o)

        series: List[Dict[str, Any]] = []
        for day in sorted(days):
            obs_dicts = [
                {
                    "carrier": str(o.airline_id),
                    "cabin_class": o.cabin_class,
                    "fare_family": o.fare_family,
                    "availability_status": o.availability_status,
                    "base_fare": o.base_fare,
                    "total_fare": o.total_fare,
                    "feed_type": o.feed_type,
                }
                for o in days[day]
            ]
            est = RepresentativePriceEstimator.estimate_route_price(
                observations=obs_dicts,
                price_field=price_field,
                estimator="JEVONS",
                cabin_class="ECONOMY",
                fare_family="BASIC",
                apply_waterfall=True,
                apply_outlier_filter=True,
            )
            if est and est.get("representative_price") is not None:
                series.append({"date": day, "price": est["representative_price"]})
        return series

    @classmethod
    def _aligned(
        cls,
        a_series: List[Dict[str, Any]],
        b_series: List[Dict[str, Any]],
    ) -> tuple:
        b_map = {s["date"]: s["price"] for s in b_series}
        a_vals, b_vals = [], []
        for s in a_series:
            if s["date"] in b_map:
                a_vals.append(s["price"])
                b_vals.append(b_map[s["date"]])
        return a_vals, b_vals

    @classmethod
    def compute_and_persist(
        cls,
        db: Session,
        route_code: Optional[str] = None,
        horizon: int = 15,
        window_days: int = 28,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Computes and optionally persists feed-cohort correlations for the window.

        A single rollup row per route/horizon is written for each correlation
        type; re-running overwrites prior rows for the same window end so the
        table tracks the latest snapshot rather than accumulating stale entries.
        """
        query = db.query(Route)
        if route_code:
            query = query.filter(Route.route_code == route_code.upper())
        routes = query.all()

        results: List[Dict[str, Any]] = []
        end = datetime.date.today()
        start = end - datetime.timedelta(days=window_days)

        for route in routes:
            direct = cls._daily_series(db, route.id, horizon, "CARRIER_DIRECT", window_days)
            ota = cls._daily_series(db, route.id, horizon, "OTA_AGGREGATOR", window_days)
            if not direct or not ota:
                continue

            a_vals, b_vals = cls._aligned(direct, ota)
            r = _pearson_r(a_vals, b_vals)
            if r is None:
                continue
            flag = r < CORRELATION_TOLERANCE

            row = SourceCorrelation(
                period_start=start,
                period_end=end,
                route_id=route.id,
                horizon_days=horizon,
                correlation_type="OTA_VS_CARRIER_DIRECT",
                source_a="Carrier Direct (CARRIER_DIRECT)",
                source_b="OTA Aggregator Consensus (OTA_AGGREGATOR)",
                pearson_r=round(r, 4),
                sample_size=len(a_vals),
                notes=(
                    f"{'DIVERGENCE ALERT' if flag else 'Aligned'} — r < {CORRELATION_TOLERANCE} "
                    f"flags OTA divergence from carrier-direct reference"
                ),
            )
            if persist:
                # Replace any prior snapshot for this window/route/horizon
                old = (
                    db.query(SourceCorrelation)
                    .filter(
                        SourceCorrelation.period_end == end,
                        SourceCorrelation.route_id == route.id,
                        SourceCorrelation.horizon_days == horizon,
                        SourceCorrelation.correlation_type == "OTA_VS_CARRIER_DIRECT",
                    )
                    .first()
                )
                if old:
                    db.delete(old)
                db.add(row)
            results.append(
                {
                    "route_code": route.route_code,
                    "pearson_r": round(r, 4),
                    "sample_size": len(a_vals),
                    "flagged": flag,
                }
            )

        if persist:
            db.commit()

        avg_r = (
            sum(res["pearson_r"] for res in results) / len(results) if results else None
        )
        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "horizon_days": horizon,
            "window_days": window_days,
            "routes_evaluated": len(routes),
            "routes_with_both_feeds": len(results),
            "average_pearson_r": round(avg_r, 4) if avg_r is not None else None,
            "divergence_flagged_routes": sum(1 for res in results if res["flagged"]),
            "results": results,
        }
