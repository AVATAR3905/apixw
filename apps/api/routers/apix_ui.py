"""APIx viewer adapter endpoints.

Serves the single-file APIx frontend (mounted at /ui) from the
observatory's real SQLite store, mirroring the upstream APIx response
contracts so the new UI runs on live data with no remote dependency:

* /routes              active domestic corridors + DGCA weights
* /index               official daily Laspeyres index (route/window/national)
* /index/headline      national headline series
* /fares/cleaned       paginated fare observations (provenance flags)
* /analytics/heatmap   fare grid per (observation date, apd)
* /analytics/elasticity fare vs advance purchase days curve
* /backtest            APIX monthly index vs MoSPI CPI benchmark
* /ingest/dummy        disabled (writes go through the live pipeline only)

Index values come from the stored official series (index_values) where the
aggregation matches (median, national/route); window scopes (route + apd)
and the min aggregation are computed live from fare_observations using the
same RepresentativePriceEstimator the official pipeline relies on.
"""

import datetime as dt
import statistics
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.session import get_db
from packages.schemas.models import (
    Airline,
    BenchmarkValue,
    FareObservation,
    IndexValue,
    Route,
    RouteWeight,
)
from packages.shared.config import settings
from packages.statistics.estimators import RepresentativePriceEstimator

router = APIRouter(tags=["APIx Viewer"])

BASE_PERIOD = dt.date.fromisoformat(settings.BASE_PERIOD)

MAX_PAGE_SIZE = 500
DEFAULT_PAGE_SIZE = 50


class RouteOut(BaseModel):
    id: int
    origin_iata: str
    destination_iata: str
    distance_km: Optional[int] = None
    dgca_traffic_weight: Optional[float] = None
    is_proxy_weight: bool
    is_active: Optional[bool] = None


class IndexPointOut(BaseModel):
    index_date: dt.date
    frequency: str
    scope: str
    aggregation_method: str
    route: Optional[str] = None
    advance_purchase_days: Optional[int] = None
    index_value: float
    route_count: int
    carrier_count: int
    observation_count: int
    base_period_ref: str
    methodology_version: str


class IndexSeriesOut(BaseModel):
    points: List[IndexPointOut]


class HeadlinePointOut(BaseModel):
    index_date: dt.date
    index_value: float


class NationalHeadlineOut(BaseModel):
    frequency: str
    aggregation_method: str
    base_period_ref: Optional[str] = None
    methodology_version: Optional[str] = None
    points: List[HeadlinePointOut]


class CleanedFareOut(BaseModel):
    id: int
    observation_date: dt.date
    origin_iata: str
    destination_iata: str
    carrier_iata: str
    flight_number: Optional[str] = None
    fare_class: Optional[str] = None
    cabin_class: Optional[str] = None
    total_fare_inr: float
    base_fare_inr: Optional[float] = None
    taxes_statutory_inr: Optional[float] = None
    udf_airport_fees_inr: Optional[float] = None
    convenience_fee_inr: Optional[float] = None
    has_full_breakdown: bool
    advance_purchase_days: int
    is_nonstop: bool
    travel_date: Optional[dt.date] = None
    source: Optional[str] = None
    is_outlier: bool
    is_imputed: bool


class FareListOut(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[CleanedFareOut]


class HeatmapCellOut(BaseModel):
    observation_date: dt.date
    advance_purchase_days: int
    min_fare_inr: float
    median_fare_inr: Optional[float] = None
    avg_fare_inr: Optional[float] = None
    max_fare_inr: float
    fare_count: int


class HeatmapOut(BaseModel):
    route: str
    date_from: dt.date
    date_to: dt.date
    cells: List[HeatmapCellOut]


class ElasticityPointOut(BaseModel):
    advance_purchase_days: int
    min_fare_inr: float
    median_fare_inr: Optional[float] = None
    avg_fare_inr: Optional[float] = None
    max_fare_inr: float
    fare_count: int


class ElasticityOut(BaseModel):
    route: str
    points: List[ElasticityPointOut]


class MonthPointOut(BaseModel):
    month: str
    apix: float
    benchmark: float
    deviation_pct: Optional[float] = None


class BacktestOut(BaseModel):
    apix_months: int
    benchmark_months: int
    method: str
    benchmark_source: str
    benchmark_version: str
    base_period_used: Optional[str] = None
    apix_base_period_ref: Optional[str] = None
    correlation: Optional[float] = None
    mean_abs_deviation_pct: Optional[float] = None
    months_compared: int
    table: List[MonthPointOut]
    apix_months_missing_benchmark: List[str]
    benchmark_months_missing_apix: List[str]


class IngestRequest(BaseModel):
    start: Optional[dt.date] = None
    end: Optional[dt.date] = None
    seed: Optional[int] = 42


class IngestOut(BaseModel):
    start: dt.date
    end: dt.date
    seed: Optional[int]
    routes: int
    total_rows: int
    by_month: Dict[str, int]
    record_types: Dict[str, int]
    has_full_breakdown: int
    without_full_breakdown: int
    note: str


def _route(session: Session, code: str) -> Route:
    route = (
        session.query(Route).filter(Route.route_code == code, Route.active.is_(True)).first()
    )
    if route is None:
        raise HTTPException(status_code=404, detail=f"Unknown route: {code}")
    return route


def _check_date_range(date_from: Optional[dt.date], date_to: Optional[dt.date]) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be <= date_to")


def _obs_dict(o: FareObservation) -> Dict[str, Any]:
    return {
        "carrier": o.airline.code,
        "base_fare": o.base_fare,
        "total_fare": o.total_fare,
        "feed_type": o.feed_type,
        "cabin_class": o.cabin_class,
        "fare_family": o.fare_family,
        "availability_status": o.availability_status,
    }


def _live_route_rep(
    session: Session,
    route: Route,
    advance_purchase_days: Optional[int],
    method: str,
) -> Dict[dt.date, Dict[str, Any]]:
    q = (
        session.query(FareObservation)
        .filter(
            FareObservation.route_id == route.id,
            FareObservation.availability_status == "AVAILABLE",
            FareObservation.cabin_class == "ECONOMY",
        )
    )
    if advance_purchase_days is not None:
        q = q.filter(FareObservation.advance_purchase_days == advance_purchase_days)

    daily: Dict[dt.date, List[FareObservation]] = {}
    for row in q.yield_per(5000):
        daily.setdefault(row.search_timestamp.date(), []).append(row)

    out: Dict[dt.date, Dict[str, Any]] = {}
    for day, rows in sorted(daily.items()):
        est = RepresentativePriceEstimator.estimate_route_price(
            [_obs_dict(r) for r in rows], price_field="base_fare", estimator="MEDIAN"
        )
        if est is None:
            continue
        if method == "min":
            rep = min(est["carrier_fares"].values())
            carriers = est["carrier_count"]
        else:
            rep = est["representative_price"]
            carriers = est["carrier_count_after_outlier_filter"]
        out[day] = {"rep": rep, "carriers": carriers, "observations": len(rows), "route_count": 1}
    return out


def _live_national_rep(session: Session, advance_purchase_days: Optional[int], method: str) -> Dict[dt.date, Dict[str, Any]]:
    routes = session.query(Route).filter(Route.active.is_(True)).all()
    merged: Dict[dt.date, Dict[str, Any]] = {}
    for route in routes:
        for day, info in _live_route_rep(session, route, advance_purchase_days, method).items():
            entry = merged.setdefault(
                day, {"rep": 0.0, "carriers": 0, "observations": 0, "route_count": 0}
            )
            entry["rep"] += info["rep"]
            entry["carriers"] += info["carriers"]
            entry["observations"] += info["observations"]
            entry["route_count"] += info["route_count"]
    for entry in merged.values():
        if entry["route_count"]:
            entry["rep"] /= entry["route_count"]
    return merged


def _index_series(
    series: Dict[dt.date, Dict[str, Any]],
    frequency: str,
    scope: str,
    method: str,
    route_code: Optional[str],
    advance_purchase_days: Optional[int],
) -> List[IndexPointOut]:
    if not series:
        return []
    base = series.get(BASE_PERIOD)
    has_ref = base is not None and base["rep"] > 0
    ref_value = base["rep"] if has_ref else None

    points: List[IndexPointOut] = []
    for day in sorted(series):
        info = series[day]
        index_value = (info["rep"] / ref_value * 100.0) if has_ref else round(info["rep"], 2)
        points.append(
            IndexPointOut(
                index_date=day,
                frequency=frequency,
                scope=scope,
                aggregation_method=method,
                route=route_code,
                advance_purchase_days=advance_purchase_days,
                index_value=round(index_value, 2),
                route_count=info["route_count"],
                carrier_count=info["carriers"],
                observation_count=info["observations"],
                base_period_ref=BASE_PERIOD.isoformat(),
                methodology_version=settings.ACTIVE_METHODOLOGY_VERSION,
            )
        )
    if frequency == "daily":
        return points

    buckets: Dict[dt.date, List[IndexPointOut]] = {}
    for p in points:
        key = p.index_date - dt.timedelta(days=p.index_date.weekday()) if frequency == "weekly" else p.index_date.replace(day=1)
        buckets.setdefault(key, []).append(p)

    out: List[IndexPointOut] = []
    for key in sorted(buckets):
        group = buckets[key]
        first = group[0]
        out.append(
            IndexPointOut(
                index_date=key,
                frequency=frequency,
                scope=first.scope,
                aggregation_method=first.aggregation_method,
                route=first.route,
                advance_purchase_days=first.advance_purchase_days,
                index_value=round(statistics.fmean(p.index_value for p in group), 2),
                route_count=max(p.route_count for p in group),
                carrier_count=max(p.carrier_count for p in group),
                observation_count=sum(p.observation_count for p in group),
                base_period_ref=first.base_period_ref,
                methodology_version=first.methodology_version,
            )
        )
    return out


# =====================================================================
# Endpoints
# =====================================================================


@router.get("/routes", response_model=List[RouteOut], response_model_exclude_none=True)
def list_routes(session: Session = Depends(get_db)) -> List[RouteOut]:
    routes = (
        session.query(Route).filter(Route.active.is_(True)).order_by(Route.route_code).all()
    )
    latest_weights: Dict[int, float] = {}
    for w in session.query(RouteWeight).order_by(RouteWeight.period, RouteWeight.id).all():
        latest_weights[w.route_id] = w.weight
    return [
        RouteOut(
            id=r.id,
            origin_iata=r.origin_airport,
            destination_iata=r.destination_airport,
            distance_km=None,
            dgca_traffic_weight=latest_weights.get(r.id),
            is_proxy_weight=latest_weights.get(r.id) is None,
            is_active=r.active,
        )
        for r in routes
    ]


@router.get("/index", response_model=IndexSeriesOut, response_model_exclude_none=True)
def get_index(
    session: Session = Depends(get_db),
    frequency: str = Query("daily"),
    aggregation_method: str = Query("median"),
    route: Optional[str] = None,
    advance_purchase_days: Optional[int] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
) -> IndexSeriesOut:
    if frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=422, detail="frequency must be daily|weekly|monthly")
    if aggregation_method not in ("median", "min"):
        raise HTTPException(status_code=422, detail="aggregation_method must be median|min")
    _check_date_range(date_from, date_to)

    if route is None:
        # National scope.
        if aggregation_method == "median":
            q = session.query(IndexValue).filter(
                IndexValue.index_series == "BASE_FARE",
                IndexValue.index_type == "HEADLINE_T15",
                IndexValue.route_id.is_(None),
            )
            if date_from is not None:
                q = q.filter(IndexValue.period_start >= date_from)
            if date_to is not None:
                q = q.filter(IndexValue.period_start <= date_to)
            rows = q.order_by(IndexValue.period_start).all()
            route_count = len(session.query(Route).filter(Route.active.is_(True)).all())
            series = {
                r.period_start: {
                    "rep": r.index_value,
                    "carriers": int(r.carrier_diversity or 0),
                    "observations": 0,
                    "route_count": route_count if r.data_completeness else 0,
                }
                for r in rows
            }
        else:
            series = _live_national_rep(session, None, "min")
            if date_from is not None:
                series = {d: v for d, v in series.items() if d >= date_from}
            if date_to is not None:
                series = {d: v for d, v in series.items() if d <= date_to}
        points = _index_series(series, frequency, "national", aggregation_method, None, None)
    else:
        route_obj = _route(session, route)
        if advance_purchase_days is None and aggregation_method == "median":
            q = session.query(IndexValue).filter(
                IndexValue.index_series == "BASE_FARE",
                IndexValue.index_type == "ROUTE_LEVEL",
                IndexValue.route_id == route_obj.id,
            )
            if date_from is not None:
                q = q.filter(IndexValue.period_start >= date_from)
            if date_to is not None:
                q = q.filter(IndexValue.period_start <= date_to)
            rows = q.order_by(IndexValue.period_start).all()
            series = {
                r.period_start: {
                    "rep": r.index_value,
                    "carriers": int(r.carrier_diversity or 0),
                    "observations": 0,
                    "route_count": 1,
                }
                for r in rows
            }
        else:
            series = _live_route_rep(session, route_obj, advance_purchase_days, aggregation_method)
            if date_from is not None:
                series = {d: v for d, v in series.items() if d >= date_from}
            if date_to is not None:
                series = {d: v for d, v in series.items() if d <= date_to}
        points = _index_series(
            series,
            frequency,
            "window" if advance_purchase_days is not None else "route",
            aggregation_method,
            route_obj.route_code,
            advance_purchase_days,
        )
    return IndexSeriesOut(points=points)


@router.get("/index/headline", response_model=NationalHeadlineOut, response_model_exclude_none=True)
def get_headline(
    session: Session = Depends(get_db),
    frequency: str = Query("monthly"),
    aggregation_method: str = Query("median"),
    series_type: str = Query("HEADLINE", pattern="^(HEADLINE|CORE)$"),
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
) -> NationalHeadlineOut:
    if frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=422, detail="frequency must be daily|weekly|monthly")
    if aggregation_method not in ("median", "min"):
        raise HTTPException(status_code=422, detail="aggregation_method must be median|min")
    _check_date_range(date_from, date_to)

    series: Dict[dt.date, Dict[str, Any]] = {}
    if aggregation_method == "median":
        q = session.query(IndexValue).filter(
            IndexValue.index_series == "BASE_FARE",
            IndexValue.index_type == "HEADLINE_T15",
            IndexValue.series_type == series_type,
            IndexValue.route_id.is_(None),
        )
        if date_from is not None:
            q = q.filter(IndexValue.period_start >= date_from)
        if date_to is not None:
            q = q.filter(IndexValue.period_start <= date_to)
        rows = q.order_by(IndexValue.period_start).all()
        for r in rows:
            series[r.period_start] = {"rep": r.index_value, "carriers": 0, "observations": 0, "route_count": 0}
    else:
        series = _live_national_rep(session, None, "min")
        if date_from is not None:
            series = {d: v for d, v in series.items() if d >= date_from}
        if date_to is not None:
            series = {d: v for d, v in series.items() if d <= date_to}

    points: List[HeadlinePointOut] = []
    if series:
        base = series.get(BASE_PERIOD)
        has_ref = base is not None and base["rep"] > 0
        ref_value = base["rep"] if has_ref else None
        daily: List[HeadlinePointOut] = [
            HeadlinePointOut(
                index_date=d,
                index_value=round((series[d]["rep"] / ref_value * 100.0) if has_ref else series[d]["rep"], 2),
            )
            for d in sorted(series)
        ]
        if frequency == "daily":
            points = daily
        else:
            buckets: Dict[dt.date, List[float]] = {}
            for p in daily:
                key = p.index_date - dt.timedelta(days=p.index_date.weekday()) if frequency == "weekly" else p.index_date.replace(day=1)
                buckets.setdefault(key, []).append(p.index_value)
            points = [HeadlinePointOut(index_date=k, index_value=round(statistics.fmean(v), 2)) for k, v in sorted(buckets.items())]

    base_period_ref = BASE_PERIOD.isoformat() if series else None
    return NationalHeadlineOut(
        frequency=frequency,
        aggregation_method=aggregation_method,
        base_period_ref=base_period_ref,
        methodology_version=settings.ACTIVE_METHODOLOGY_VERSION if series else None,
        points=points,
    )


@router.get("/fares/cleaned", response_model=FareListOut, response_model_exclude_none=True)
def list_cleaned_fares(
    session: Session = Depends(get_db),
    route: Optional[str] = None,
    carrier: Optional[str] = None,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    travel_date_from: Optional[dt.date] = None,
    travel_date_to: Optional[dt.date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
) -> FareListOut:
    _check_date_range(date_from, date_to)
    _check_date_range(travel_date_from, travel_date_to)
    q = session.query(FareObservation)

    route_obj = None
    if route is not None:
        route_obj = _route(session, route)
        q = q.filter(FareObservation.route_id == route_obj.id)
    if carrier is not None:
        q = q.join(FareObservation.airline).filter(Airline.code == carrier)
    if date_from is not None:
        q = q.filter(func.date(FareObservation.search_timestamp) >= date_from)
    if date_to is not None:
        q = q.filter(func.date(FareObservation.search_timestamp) <= date_to)
    if travel_date_from is not None:
        q = q.filter(FareObservation.travel_date >= travel_date_from)
    if travel_date_to is not None:
        q = q.filter(FareObservation.travel_date <= travel_date_to)

    total = q.count()
    rows = (
        q.order_by(FareObservation.search_timestamp.desc(), FareObservation.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: List[CleanedFareOut] = []
    for o in rows:
        breakdown = all(
            v is not None
            for v in (o.base_fare, o.fuel_surcharge, o.tax_amount, o.development_fee, o.convenience_fee)
        )
        items.append(
            CleanedFareOut(
                id=o.id,
                observation_date=o.search_timestamp.date(),
                origin_iata=o.route.origin_airport,
                destination_iata=o.route.destination_airport,
                carrier_iata=o.airline.code,
                flight_number=o.flight_number,
                fare_class=o.fare_family,
                cabin_class=o.cabin_class,
                total_fare_inr=round(o.total_fare, 2),
                base_fare_inr=round(o.base_fare, 2),
                taxes_statutory_inr=round((o.tax_amount or 0.0) + (o.fuel_surcharge or 0.0), 2),
                udf_airport_fees_inr=round(o.development_fee or 0.0, 2),
                convenience_fee_inr=round(o.convenience_fee or 0.0, 2),
                has_full_breakdown=breakdown,
                advance_purchase_days=o.advance_purchase_days,
                is_nonstop=bool(o.stops == 0),
                travel_date=o.travel_date,
                source=o.feed_type,
                is_outlier=bool(o.quality_status not in ("ACCEPT", "ACCEPT_WITH_WARNING")),
                is_imputed=bool(o.is_synthetic),
            )
        )
    return FareListOut(page=page, page_size=page_size, total=total, items=items)


@router.get("/analytics/heatmap", response_model=HeatmapOut, response_model_exclude_none=True)
def heatmap(
    session: Session = Depends(get_db),
    route: str = Query(...),
    date_from: dt.date = Query(...),
    date_to: dt.date = Query(...),
) -> HeatmapOut:
    route_obj = _route(session, route)
    _check_date_range(date_from, date_to)
    rows = (
        session.query(FareObservation)
        .filter(
            FareObservation.route_id == route_obj.id,
            FareObservation.availability_status == "AVAILABLE",
            FareObservation.cabin_class == "ECONOMY",
            FareObservation.stops == 0,
            FareObservation.total_fare > 0,
            func.date(FareObservation.search_timestamp) >= date_from,
            func.date(FareObservation.search_timestamp) <= date_to,
        )
        .all()
    )
    cells_map: Dict[tuple, List[float]] = {}
    for o in rows:
        cells_map.setdefault((o.search_timestamp.date(), o.advance_purchase_days), []).append(o.total_fare)
    cells = [
        HeatmapCellOut(
            observation_date=d,
            advance_purchase_days=apd,
            min_fare_inr=round(min(v), 2),
            median_fare_inr=round(statistics.median(v), 2),
            avg_fare_inr=round(statistics.fmean(v), 2),
            max_fare_inr=round(max(v), 2),
            fare_count=len(v),
        )
        for (d, apd), v in sorted(cells_map.items())
    ]
    return HeatmapOut(route=route_obj.route_code, date_from=date_from, date_to=date_to, cells=cells)


@router.get("/analytics/elasticity", response_model=ElasticityOut, response_model_exclude_none=True)
def elasticity(
    session: Session = Depends(get_db),
    route: str = Query(...),
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
) -> ElasticityOut:
    route_obj = _route(session, route)
    _check_date_range(date_from, date_to)
    q = session.query(FareObservation).filter(
        FareObservation.route_id == route_obj.id,
        FareObservation.availability_status == "AVAILABLE",
        FareObservation.cabin_class == "ECONOMY",
        FareObservation.stops == 0,
        FareObservation.total_fare > 0,
    )
    if date_from is not None:
        q = q.filter(func.date(FareObservation.search_timestamp) >= date_from)
    if date_to is not None:
        q = q.filter(func.date(FareObservation.search_timestamp) <= date_to)
    rows = q.all()
    grouped: Dict[int, List[float]] = {}
    for o in rows:
        grouped.setdefault(o.advance_purchase_days, []).append(o.total_fare)
    points = [
        ElasticityPointOut(
            advance_purchase_days=apd,
            min_fare_inr=round(min(v), 2),
            median_fare_inr=round(statistics.median(v), 2),
            avg_fare_inr=round(statistics.fmean(v), 2),
            max_fare_inr=round(max(v), 2),
            fare_count=len(v),
        )
        for apd, v in sorted(grouped.items())
    ]
    return ElasticityOut(route=route_obj.route_code, points=points)


@router.get("/backtest", response_model=BacktestOut, response_model_exclude_none=True)
def backtest(
    session: Session = Depends(get_db),
    method: str = Query("median"),
    base_period: Optional[str] = None,
    start: Optional[dt.date] = None,
    end: Optional[dt.date] = None,
) -> BacktestOut:
    if method not in ("median", "min"):
        raise HTTPException(status_code=422, detail="method must be median|min")
    _check_date_range(start, end)

    if method == "median":
        q = session.query(IndexValue).filter(
            IndexValue.index_series == "BASE_FARE",
            IndexValue.index_type == "HEADLINE_T15",
            IndexValue.route_id.is_(None),
        )
    else:
        q = session.query(IndexValue).filter(
            IndexValue.index_series == "TOTAL_PRICE",
            IndexValue.index_type == "HEADLINE_T15",
            IndexValue.route_id.is_(None),
        )
    if start is not None:
        q = q.filter(IndexValue.period_start >= start)
    if end is not None:
        q = q.filter(IndexValue.period_start <= end)
    rows = q.order_by(IndexValue.period_start).all()

    apix_monthly: Dict[str, List[float]] = {}
    for r in rows:
        apix_monthly.setdefault(r.period_start.strftime("%Y-%m"), []).append(r.index_value)

    benchmarks = {
        b.period: b.value
        for b in session.query(BenchmarkValue).filter(BenchmarkValue.period >= "2025-01").all()
    }

    apix_months = sorted(apix_monthly)
    benchmark_months = sorted(benchmarks)
    common = [m for m in apix_months if m in benchmarks]
    table: List[MonthPointOut] = []
    for m in common:
        apix_val = statistics.fmean(apix_monthly[m])
        bench_val = benchmarks[m]
        deviation = ((apix_val - bench_val) / bench_val * 100.0) if bench_val else None
        table.append(
            MonthPointOut(
                month=m,
                apix=round(apix_val, 2),
                benchmark=round(bench_val, 2),
                deviation_pct=round(deviation, 2) if deviation is not None else None,
            )
        )

    correlation: Optional[float] = None
    if len(common) >= 2:
        try:
            import statistics as _stat

            xs = [_stat.fmean(apix_monthly[m]) for m in common]
            ys = [benchmarks[m] for m in common]
            correlation = round(
                _stat.correlation(xs, ys),
                4,
            )
        except Exception:
            correlation = None

    mean_abs_dev_pct: Optional[float] = None
    if table:
        vals = [t.deviation_pct for t in table if t.deviation_pct is not None]
        if vals:
            mean_abs_dev_pct = round(statistics.fmean(abs(v) for v in vals), 2)

    return BacktestOut(
        apix_months=len(apix_months),
        benchmark_months=len(benchmark_months),
        method=method,
        benchmark_source="MoSPI CPI Passenger Transport Services (item 07.3, combined rail/air/road -- MoSPI does not publish a standalone domestic-airfare-only index)",
        benchmark_version="CPI_PASSENGER_TRANSPORT_SERVICES_2026",
        base_period_used=base_period or "2026-08",
        apix_base_period_ref=BASE_PERIOD.isoformat(),
        correlation=correlation,
        mean_abs_deviation_pct=mean_abs_dev_pct,
        months_compared=len(common),
        table=table,
        apix_months_missing_benchmark=[m for m in apix_months if m not in benchmarks],
        benchmark_months_missing_apix=[m for m in benchmark_months if m not in apix_monthly],
    )


@router.post("/ingest/dummy", response_model=IngestOut)
def ingest_dummy(
    body: IngestRequest,
    session: Session = Depends(get_db),
) -> IngestOut:
    start = body.start or dt.date.today() - dt.timedelta(days=30)
    end = body.end or dt.date.today()
    routes = session.query(Route).filter(Route.active.is_(True)).count()
    return IngestOut(
        start=start,
        end=end,
        seed=body.seed,
        routes=routes,
        total_rows=0,
        by_month={},
        record_types={},
        has_full_breakdown=0,
        without_full_breakdown=0,
        note="Dummy ingest is disabled: the observatory only writes real scraped data through its live collection pipeline.",
    )
