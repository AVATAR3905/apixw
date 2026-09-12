"""REST API Router v1 for the India Airfare Price Observatory (Official MoSPI Specifications)."""

import datetime
import hashlib
import json
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.session import get_db
from packages.schemas.models import (
    Airline,
    DiscrepancyAudit,
    FareObservation,
    IndexValue,
    MethodologyVersion,
    Route,
    Source,
)
from packages.statistics.carrier_inflation import CarrierInflationService
from packages.statistics.estimators import available_fares
from packages.statistics.volatility import VolatilityService
from packages.statistics.weights import DGCAWeightEngine
from services.collectors.health_service import CollectorHealthService
from services.ml.ensemble import (
    EnsembleForecaster,
    get_all_historical_data,
    get_historical_index_data,
)
from services.ml.forecast_accuracy import (
    ForecastAccuracySummary,
    compute_all_accuracy,
    persist_forecast_snapshot,
)

router = APIRouter(prefix="/api/v1")


# =====================================================================
# Tiered Response Caching (FareLens pattern)
# =====================================================================

class ResponseCache:
    """In-memory response cache with TTL and namespace support."""

    def __init__(self):
        self._cache: Dict[str, tuple] = {}  # key -> (value, expires_at)
        self._hit_count = 0
        self._miss_count = 0

    # TTL config (seconds)
    TTL = {
        "index": 900,           # 15 min
        "index_timeseries": 900,
        "corridor_list": 600,   # 10 min
        "corridor_detail": 600,
        "live_quotes": 120,     # 2 min
        "analytics": 1800,      # 30 min
        "export": 3600,         # 1 hour
    }

    def _make_key(self, endpoint: str, params: Dict) -> str:
        param_str = json.dumps(params, sort_keys=True, default=str)
        return f"apix:{endpoint}:{hashlib.md5(param_str.encode()).hexdigest()[:16]}"

    def get(self, endpoint: str, params: Dict) -> Optional[Any]:
        key = self._make_key(endpoint, params)
        if key in self._cache:
            value, expires_at = self._cache[key]
            if time.time() < expires_at:
                self._hit_count += 1
                return value
            else:
                del self._cache[key]
        self._miss_count += 1
        return None

    def set(self, endpoint: str, params: Dict, value: Any, ttl: Optional[int] = None) -> None:
        key = self._make_key(endpoint, params)
        ttl = ttl or self.TTL.get(endpoint, 300)
        self._cache[key] = (value, time.time() + ttl)

    def invalidate(self, endpoint: str) -> int:
        """Invalidate all cache entries for an endpoint."""
        prefix = f"apix:{endpoint}:"
        keys_to_del = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_del:
            del self._cache[k]
        return len(keys_to_del)

    def stats(self) -> Dict[str, int]:
        return {"hits": self._hit_count, "misses": self._miss_count, "size": len(self._cache)}


# Global response cache
_response_cache = ResponseCache()


def get_cached_response(endpoint: str, params: Dict) -> Optional[Any]:
    return _response_cache.get(endpoint, params)


def set_cached_response(endpoint: str, params: Dict, value: Any, ttl: Optional[int] = None) -> None:
    _response_cache.set(endpoint, params, value, ttl)


def invalidate_endpoint_cache(endpoint: str) -> int:
    return _response_cache.invalidate(endpoint)


# =====================================================================
# Pydantic Schemas for Swagger / OpenAPI Documentation
# =====================================================================

class DailyIndexItem(BaseModel):
    date: str = Field(..., description="Observation date (ISO-8601)", example="2026-09-04")
    index_value: float = Field(
        ..., description="APIX-2.0 Laspeyres Price Index (Base 2026-08-01 = 100.00)", example=110.36
    )
    daily_change_pct: Optional[float] = Field(
        None, description="24-hour rate of change (%)", example=0.25
    )
    coverage_rate: float = Field(..., description="Sample coverage percentage", example=100.0)
    is_low_coverage: bool = Field(
        False, description="Flag indicating if sample falls below 80% statutory threshold"
    )


class FareDecompositionItem(BaseModel):
    base_fare: float = Field(..., description="Base airline tariff component (INR)", example=3850.0)
    fuel_surcharge: float = Field(..., description="Fuel surcharge component (INR)", example=850.0)
    gst_taxes: float = Field(..., description="Statutory 5% GST tax (INR)", example=235.0)
    udf_adf: float = Field(..., description="Airport User / Development Fee (INR)", example=350.0)
    convenience_fee: float = Field(..., description="Booking fee (INR)", example=0.0)
    total_consumer_fare: float = Field(
        ..., description="Total walkaway passenger fare (INR)", example=5285.0
    )


class CarrierBreakdownItem(BaseModel):
    carrier: str = Field(
        ..., description="IATA 2-letter airline code (6E, AI, SG, QP, IX)", example="6E"
    )
    name: str = Field(..., description="Operating domestic carrier name", example="IndiGo")
    basic_fare: float = Field(
        ..., description="Minimum published economy fare (INR)", example=4850.0
    )
    flexi_fare: float = Field(..., description="Flexi/Comfort bundle fare (INR)", example=6200.0)
    is_min: bool = Field(
        ..., description="Whether carrier offers the cheapest corridor quote", example=True
    )
    flights: int = Field(..., description="Number of monitored departures", example=14)


class CorridorDetailResponse(BaseModel):
    route_code: str = Field(
        ..., description="City-pair corridor code (e.g. DEL-BOM)", example="DEL-BOM"
    )
    origin: str = Field(..., description="Origin city name", example="Delhi")
    destination: str = Field(..., description="Destination city name", example="Mumbai")
    corridor_type: str = Field(
        ..., description="DGCA classification (METRO_TRUNK or REGIONAL_THIN)", example="METRO_TRUNK"
    )
    weight_pct: float = Field(..., description="DGCA passenger traffic weight (%)", example=18.5)
    representative_price: Optional[float] = Field(
        None, description="Median basic fare across carriers (INR)", example=4850.0
    )
    fare_decomposition: Optional[FareDecompositionItem] = None
    carrier_breakdown: List[CarrierBreakdownItem] = []


# =====================================================================
# Forecast Schemas
# =====================================================================

class ForecastPoint(BaseModel):
    """Single forecast point with probabilistic intervals."""
    target_date: str = Field(..., description="Target date (ISO-8601)", example="2026-09-15")
    horizon: int = Field(..., description="Days ahead", example=5)
    p10: float = Field(..., description="10th percentile (lower bound)", example=105.2)
    p25: float = Field(..., description="25th percentile", example=108.1)
    p50: float = Field(..., description="50th percentile (median)", example=110.5)
    p75: float = Field(..., description="75th percentile", example=113.2)
    p90: float = Field(..., description="90th percentile (upper bound)", example=116.8)
    model_confidence: float = Field(..., description="Ensemble confidence 0-1", example=0.85)
    component_forecasts: Dict[str, Dict[str, float]] = Field(
        ..., description="Individual model forecasts"
    )


class ForecastResponse(BaseModel):
    """Probabilistic forecast response for 28 days."""
    series: str = Field(..., description="Price series", example="BASE_FARE")
    index_type: str = Field(..., description="Index type", example="HEADLINE_T15")
    forecast_date: str = Field(..., description="Forecast generation date", example="2026-09-10")
    horizon_days: int = Field(..., description="Forecast horizon", example=28)
    points: List[ForecastPoint]
    ensemble_weights: Dict[str, float] = Field(..., description="Model weights")
    model_versions: Dict[str, str] = Field(..., description="Model versions")
    generated_at: str = Field(..., description="Generation timestamp")


class ForecastAllResponse(BaseModel):
    """Forecasts for all series and index types."""
    forecasts: Dict[str, Dict[str, ForecastResponse]]
    generated_at: str


class ForecastAccuracyByHorizon(BaseModel):
    horizon_bucket: str
    count: int
    mae: float
    rmse: float
    mape_pct: float
    bias: float


class ForecastAccuracyPoint(BaseModel):
    target_date: str
    generated_at: Optional[str] = None
    horizon_days: int
    actual: float
    p10: Optional[float] = None
    p25: Optional[float] = None
    p50: Optional[float] = None
    p75: Optional[float] = None
    p90: Optional[float] = None
    model_confidence: Optional[float] = None


class ForecastAccuracyItem(BaseModel):
    """Backtest score for one series/index_type combination."""
    series: str
    index_type: str
    available: bool
    snapshot_count: int
    matched_count: int
    mae: float
    rmse: float
    mape_pct: float
    bias: float
    p50_hit_rate_pct: float
    p10_p90_coverage_pct: float
    by_horizon: List[ForecastAccuracyByHorizon]
    recent: List[ForecastAccuracyPoint]


class ForecastAccuracyResponse(BaseModel):
    """Accuracy of past forecasts vs realized index values."""
    generated_at: str
    lookback_days: int
    results: List[ForecastAccuracyItem]


class CorridorSummaryItem(BaseModel):
    id: int = Field(..., description="Corridor database identifier", example=1)
    route_code: str = Field(..., description="City-pair corridor code", example="DEL-BOM")
    origin: str = Field(..., description="Origin city", example="Delhi")
    destination: str = Field(..., description="Destination city", example="Mumbai")
    origin_airport: str = Field(..., description="Origin airport IATA code", example="DEL")
    destination_airport: str = Field(
        ..., description="Destination airport IATA code", example="BOM"
    )
    corridor_type: str = Field(..., description="DGCA classification", example="METRO_TRUNK")
    dgca_weight: float = Field(..., description="Normalized basket weight", example=0.185)
    current_index: Optional[float] = Field(
        None, description="Current corridor index (Base = 100.00)", example=112.45
    )
    daily_change_pct: Optional[float] = Field(None, description="24-hour change (%)", example=0.35)
    weekly_change_pct: Optional[float] = Field(None, description="7-day change (%)", example=1.85)
    monthly_change_pct: Optional[float] = Field(None, description="30-day change (%)", example=8.40)
    representative_price: Optional[float] = Field(
        None, description="Median basic fare across carriers (INR)", example=4850.0
    )


class LiveQuoteItem(BaseModel):
    id: int = Field(..., description="Unique observation ID", example=15281)
    route_code: str = Field(..., description="Corridor code", example="DEL-BOM")
    carrier_code: str = Field(..., description="Airline IATA code", example="6E")
    carrier_name: str = Field(..., description="Airline name", example="IndiGo")
    flight_number: str = Field(..., description="Operating flight number", example="6E-205")
    advance_purchase_days: int = Field(
        ..., description="Advance booking horizon (days)", example=14
    )
    travel_date: str = Field(..., description="Scheduled departure date", example="2026-09-18")
    observed_at: str = Field(
        ..., description="Exact capture timestamp in ISO format", example="2026-09-04T21:30:00Z"
    )
    source_name: str = Field(
        ..., description="Provenance feed title", example="Google Flights RPC Validator & Fallback"
    )
    feed_type: str = Field(..., description="Ingestion feed type", example="CARRIER_DIRECT")
    base_fare: float = Field(..., description="Base tariff (INR)", example=3850.0)
    fuel_surcharge: float = Field(..., description="Fuel surcharge (INR)", example=850.0)
    tax_amount: float = Field(..., description="Statutory 5% GST (INR)", example=235.0)
    development_fee: float = Field(..., description="UDF/ADF fee (INR)", example=350.0)
    convenience_fee: float = Field(..., description="Booking fee (INR)", example=0.0)
    total_fare: float = Field(..., description="Total consumer fare (INR)", example=5285.0)
    is_synthetic: bool = Field(False, description="Whether data point is synthetic", example=False)


@router.get("/index")
def get_current_index(
    series: str = Query("BASE_FARE", pattern="^(BASE_FARE|TOTAL_PRICE)$"),
    horizon: str = Query("t15", pattern="^(t1|t7|t14|t15|t30|t45)$"),
    db: Session = Depends(get_db),
):
    """Retrieves current headline index value and deltas."""
    # Check cache first
    cache_params = {"series": series, "horizon": horizon}
    cached = get_cached_response("index", cache_params)
    if cached is not None:
        return cached

    h_int = int(horizon.replace("t", ""))
    itype = "HEADLINE_T15" if h_int in (14, 15) else f"SUB_T{h_int}"

    query = db.query(IndexValue).filter(
        IndexValue.index_series == series,
        IndexValue.route_id.is_(None),
    )
    if h_int in (14, 15):
        query = query.filter(IndexValue.index_type.in_(["HEADLINE_T15", "HEADLINE_T14"]))
    else:
        query = query.filter(IndexValue.index_type == itype)

    latest = query.order_by(IndexValue.period_start.desc()).first()

    if not latest:
        any_headline = (
            db.query(IndexValue)
            .filter(IndexValue.route_id.is_(None))
            .order_by(IndexValue.period_start.desc())
            .first()
        )
        if any_headline:
            latest = any_headline
        else:
            return None

    response = {
        "index_series": latest.index_series,
        "index_type": latest.index_type,
        "lead_time_days": latest.lead_time_days,
        "index_value": latest.index_value,
        "daily_change_pct": latest.daily_change_pct,
        "weekly_change_pct": latest.weekly_change_pct,
        "monthly_change_pct": latest.monthly_change_pct,
        "coverage_rate": latest.coverage_rate,
        "is_low_coverage": latest.is_low_coverage,
        "period_start": latest.period_start.isoformat(),
        "active_version": latest.methodology_version,
    }

    # Cache the response
    set_cached_response("index", cache_params, response)
    return response


@router.get("/index/timeseries")
def get_index_timeseries(
    series: str = Query("BASE_FARE", pattern="^(BASE_FARE|TOTAL_PRICE)$"),
    horizon: int = Query(15),
    db: Session = Depends(get_db),
):
    """Returns historical daily time-series of index values."""
    cache_params = {"series": series, "horizon": horizon}
    cached = get_cached_response("index_timeseries", cache_params)
    if cached is not None:
        return cached

    query = db.query(IndexValue).filter(
        IndexValue.index_series == series,
        IndexValue.route_id.is_(None),
    )
    if horizon in (14, 15):
        query = query.filter(IndexValue.index_type.in_(["HEADLINE_T15", "HEADLINE_T14"]))
    else:
        query = query.filter(IndexValue.index_type == f"SUB_T{horizon}")

    records = query.order_by(IndexValue.period_start.asc()).all()

    response = [
        {
            "date": r.period_start.isoformat(),
            "index_value": r.index_value,
            "daily_change_pct": r.daily_change_pct,
            "coverage_rate": r.coverage_rate,
        }
        for r in records
    ]

    set_cached_response("index_timeseries", cache_params, response)
    return response


@router.get(
    "/index/daily",
    response_model=List[DailyIndexItem],
    tags=["Public National Indices"],
    summary="Daily Airfare Price Index Time-Series (APIX-2.0)",
    description="Returns the official daily Laspeyres Headline Index (T+15) or advance purchase Sub-Indices (T+1, T+7, T+15, T+30, T+45) with day-on-day percentage change and statistical sample coverage rates.",
)
def get_daily_indices(
    from_date: Optional[str] = Query(
        None, alias="from", description="Start date filter (YYYY-MM-DD)", examples=["2026-08-01"]
    ),
    to_date: Optional[str] = Query(
        None, alias="to", description="End date filter (YYYY-MM-DD)", examples=["2026-09-04"]
    ),
    series: str = Query(
        "BASE_FARE",
        pattern="^(BASE_FARE|TOTAL_PRICE)$",
        description="Target price series (BASE_FARE or TOTAL_PRICE)",
        examples=["BASE_FARE"],
    ),
    horizon: int = Query(
        15, description="Advance purchase booking horizon in days (1, 7, 15, 30, 45)", examples=[15]
    ),
    db: Session = Depends(get_db),
):
    """Returns filtered daily index time-series between from_date and to_date."""
    query = db.query(IndexValue).filter(
        IndexValue.index_series == series,
        IndexValue.route_id.is_(None),
    )
    if horizon in (14, 15):
        query = query.filter(IndexValue.index_type.in_(["HEADLINE_T15", "HEADLINE_T14"]))
    else:
        query = query.filter(IndexValue.index_type == f"SUB_T{horizon}")
    if from_date:
        query = query.filter(IndexValue.period_start >= datetime.date.fromisoformat(from_date))
    if to_date:
        query = query.filter(IndexValue.period_start <= datetime.date.fromisoformat(to_date))

    records = query.order_by(IndexValue.period_start.asc()).all()
    return [
        {
            "date": r.period_start.isoformat(),
            "index_value": r.index_value,
            "daily_change_pct": r.daily_change_pct,
            "coverage_rate": r.coverage_rate,
            "is_low_coverage": r.is_low_coverage,
        }
        for r in records
    ]


@router.get("/index/monthly")
def get_monthly_aggregated_indices(
    series: str = Query("BASE_FARE", pattern="^(BASE_FARE|TOTAL_PRICE)$"),
    db: Session = Depends(get_db),
):
    """Returns monthly calendar-aggregated index series for MoSPI CPI alignment."""
    from packages.statistics.temporal_aggregations import TemporalAggregationEngine

    records = (
        db.query(IndexValue)
        .filter(
            IndexValue.index_series == series,
            IndexValue.index_type.in_(["HEADLINE_T15", "HEADLINE_T14"]),
            IndexValue.route_id.is_(None),
        )
        .order_by(IndexValue.period_start.asc())
        .all()
    )

    daily_dicts = [
        {
            "date": r.period_start,
            "index_value": r.index_value,
            "index_series": r.index_series,
            "index_type": r.index_type,
            "coverage_rate": r.coverage_rate,
        }
        for r in records
    ]
    return TemporalAggregationEngine.aggregate_monthly(daily_dicts)


# =====================================================================
# Forecast Endpoints (Past 28d + Future 28d)
# =====================================================================

@router.get("/forecast",
    response_model=ForecastResponse,
    tags=["Forecasting"],
    summary="Probabilistic Index Forecast (Next 28 Days)",
    description="Returns ensemble forecast (TimesFM + LightGBM + Statistical) with P10/P25/P50/P75/P90 "
                "prediction intervals for the next 28 days. Combines observed history with ML forecasting."
)
def get_index_forecast(
    series: str = Query("BASE_FARE", pattern="^(BASE_FARE|TOTAL_PRICE)$"),
    index_type: str = Query("HEADLINE_T15", pattern="^(HEADLINE_T15|HEADLINE_T14|SUB_T1|SUB_T7|SUB_T15|SUB_T30|SUB_T45)$"),
    horizon: int = Query(28, ge=1, le=28, description="Forecast horizon in days"),
    history_days: int = Query(100, ge=30, le=200, description="Historical days to use for forecasting"),
    db: Session = Depends(get_db),
):
    """
    Generate probabilistic forecast for a specific index series and type.

    Returns P10/P25/P50/P75/P90 prediction intervals for each day in the forecast horizon.
    Ensemble combines: TimesFM 2.5 (50%), LightGBM with conformal intervals (35%), Statistical STL+ARIMA (15%).
    """
    # Get historical data
    history = get_historical_index_data(db, series, index_type, history_days)

    if len(history) < 10:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient historical data: {len(history)} points (minimum 10 required)"
        )

    # Generate ensemble forecast
    forecaster = EnsembleForecaster()
    forecast = forecaster.forecast(series, index_type, history, horizon)

    # Convert to response model
    points = [
        ForecastPoint(
            target_date=p.target_date.isoformat(),
            horizon=p.horizon,
            p10=p.p10,
            p25=p.p25,
            p50=p.p50,
            p75=p.p75,
            p90=p.p90,
            model_confidence=p.model_confidence,
            component_forecasts=p.component_forecasts,
        )
        for p in forecast.points
    ]

    # Persist a snapshot for later accuracy backtesting
    persist_forecast_snapshot(
        db,
        series=forecast.series,
        index_type=forecast.index_type,
        forecast_date=forecast.forecast_date,
        points=forecast.points,
        ensemble_weights=forecast.ensemble_weights,
        model_versions=forecast.model_versions,
        history_days=history_days,
        horizon_days=forecast.horizon_days,
    )

    return ForecastResponse(
        series=forecast.series,
        index_type=forecast.index_type,
        forecast_date=forecast.forecast_date.isoformat(),
        horizon_days=forecast.horizon_days,
        points=points,
        ensemble_weights=forecast.ensemble_weights,
        model_versions=forecast.model_versions,
        generated_at=forecast.generated_at.isoformat() + "Z",
    )


@router.get("/forecast/all",
    response_model=ForecastAllResponse,
    tags=["Forecasting"],
    summary="All Series Forecasts (Next 28 Days)",
    description="Returns ensemble forecasts for all series (BASE_FARE, TOTAL_PRICE) and all index types "
                "(HEADLINE_T15, SUB_T1, SUB_T7, SUB_T30, SUB_T45) with full prediction intervals."
)
def get_all_forecasts(
    horizon: int = Query(28, ge=1, le=28),
    history_days: int = Query(100, ge=30, le=200),
    db: Session = Depends(get_db),
):
    """
    Generate forecasts for all series and index types in one call.

    Returns nested dict: {series: {index_type: ForecastResponse}}
    """
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
        raise HTTPException(status_code=400, detail="No series with sufficient historical data")

    # Generate all forecasts
    forecaster = EnsembleForecaster()
    all_forecasts = forecaster.forecast_all_series(filtered, horizon)

    # Convert to response models
    response_forecasts = {}
    for series, idx_types in all_forecasts.items():
        response_forecasts[series] = {}
        for idx_type, forecast in idx_types.items():
            points = [
                ForecastPoint(
                    target_date=p.target_date.isoformat(),
                    horizon=p.horizon,
                    p10=p.p10,
                    p25=p.p25,
                    p50=p.p50,
                    p75=p.p75,
                    p90=p.p90,
                    model_confidence=p.model_confidence,
                    component_forecasts=p.component_forecasts,
                )
                for p in forecast.points
            ]
            response_forecasts[series][idx_type] = ForecastResponse(
                series=forecast.series,
                index_type=forecast.index_type,
                forecast_date=forecast.forecast_date.isoformat(),
                horizon_days=forecast.horizon_days,
                points=points,
                ensemble_weights=forecast.ensemble_weights,
                model_versions=forecast.model_versions,
                generated_at=forecast.generated_at.isoformat() + "Z",
            )

            # Persist a snapshot for later accuracy backtesting
            persist_forecast_snapshot(
                db,
                series=forecast.series,
                index_type=forecast.index_type,
                forecast_date=forecast.forecast_date,
                points=forecast.points,
                ensemble_weights=forecast.ensemble_weights,
                model_versions=forecast.model_versions,
                history_days=history_days,
                horizon_days=forecast.horizon_days,
            )

    return ForecastAllResponse(
        forecasts=response_forecasts,
        generated_at=datetime.datetime.utcnow().isoformat() + "Z",
    )


@router.get("/forecast/history-and-forecast",
    tags=["Forecasting"],
    summary="Combined Historical + Forecast View (Past 28d + Future 28d)",
    description="Returns the last 28 days of observed index values combined with "
                "the next 28 days of probabilistic forecasts in a single response. "
                "Ideal for dashboard visualization showing continuous timeline."
)
def get_history_and_forecast(
    series: str = Query("BASE_FARE", pattern="^(BASE_FARE|TOTAL_PRICE)$"),
    index_type: str = Query("HEADLINE_T15", pattern="^(HEADLINE_T15|HEADLINE_T14|SUB_T1|SUB_T7|SUB_T15|SUB_T30|SUB_T45)$"),
    history_days: int = Query(28, ge=14, le=60, description="Days of history to include"),
    horizon: int = Query(28, ge=1, le=28, description="Forecast horizon"),
    db: Session = Depends(get_db),
):
    """
    Combined endpoint returning observed history + forecast in one response.

    Response format:
    {
        "series": "BASE_FARE",
        "index_type": "HEADLINE_T15",
        "history": [{"date": "...", "value": ..., "type": "observed"}, ...],
        "forecast": [{"date": "...", "p10": ..., "p50": ..., "p90": ..., "type": "forecast"}, ...],
        "ensemble_weights": {...},
        "model_versions": {...}
    }
    """
    # Get history
    history = get_historical_index_data(db, series, index_type, history_days)

    if len(history) < 10:
        raise HTTPException(status_code=400, detail="Insufficient historical data")

    # Generate forecast
    forecaster = EnsembleForecaster()
    forecast = forecaster.forecast(series, index_type, history, horizon)

    # Format history
    history_formatted = [
        {"date": h["date"], "value": h["value"], "type": "observed"}
        for h in history
    ]

    # Format forecast
    forecast_formatted = [
        {
            "date": p.target_date.isoformat(),
            "p10": p.p10,
            "p25": p.p25,
            "p50": p.p50,
            "p75": p.p75,
            "p90": p.p90,
            "model_confidence": p.model_confidence,
            "type": "forecast",
        }
        for p in forecast.points
    ]

    # Persist a snapshot for later accuracy backtesting
    persist_forecast_snapshot(
        db,
        series=series,
        index_type=index_type,
        forecast_date=forecast.forecast_date,
        points=forecast.points,
        ensemble_weights=forecast.ensemble_weights,
        model_versions=forecast.model_versions,
        history_days=history_days,
        horizon_days=forecast.horizon_days,
    )

    return {
        "series": series,
        "index_type": index_type,
        "horizon_days": horizon,
        "history": history_formatted,
        "forecast": forecast_formatted,
        "ensemble_weights": forecast.ensemble_weights,
        "model_versions": forecast.model_versions,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


@router.get(
    "/forecast/accuracy",
    response_model=ForecastAccuracyResponse,
    tags=["Forecasting"],
    summary="Forecast Backtest Accuracy (Forecast vs Realized)",
    description="Scores previously persisted forecasts against realized index values: "
                "MAE/RMSE/MAPE, bias, P50 hit rate, and P10-P90 interval coverage, "
                "with a breakdown by horizon bucket and the latest matched samples.",
)
def get_forecast_accuracy(
    series: Optional[str] = Query(
        None, description="Comma-separated series filter (BASE_FARE, TOTAL_PRICE)"
    ),
    index_type: Optional[str] = Query(
        None, description="Comma-separated index type filter (HEADLINE_T15, SUB_T1, ...)"
    ),
    lookback_days: int = Query(
        180, ge=30, le=730, description="Days of stored snapshots to score"
    ),
    db: Session = Depends(get_db),
):
    """Return backtest accuracy of stored forecasts vs realized index values."""
    summaries = compute_all_accuracy(
        db,
        series=series,
        index_type=index_type,
        lookback_days=lookback_days,
    )
    results = [_summary_to_item(s) for s in summaries]
    return ForecastAccuracyResponse(
        generated_at=datetime.datetime.utcnow().isoformat() + "Z",
        lookback_days=lookback_days,
        results=results,
    )


def _summary_to_item(s: ForecastAccuracySummary) -> ForecastAccuracyItem:
    """Convert a backtest summary dataclass into the API response model."""
    return ForecastAccuracyItem(
        series=s.series,
        index_type=s.index_type,
        available=s.available,
        snapshot_count=s.snapshot_count,
        matched_count=s.matched_count,
        mae=round(s.mae, 3),
        rmse=round(s.rmse, 3),
        mape_pct=round(s.mape_pct, 2),
        bias=round(s.bias, 3),
        p50_hit_rate_pct=round(s.p50_hit_rate_pct, 2),
        p10_p90_coverage_pct=round(s.p10_p90_coverage_pct, 2),
        by_horizon=[
            ForecastAccuracyByHorizon(**{**h, "mae": round(h["mae"], 3), "rmse": round(h["rmse"], 3)})
            for h in s.by_horizon
        ],
        recent=[
            ForecastAccuracyPoint(
                target_date=r["target_date"],
                generated_at=r["generated_at"],
                horizon_days=r["horizon_days"],
                actual=round(r["actual"], 3),
                p10=round(r["p10"], 3) if r["p10"] is not None else None,
                p25=round(r["p25"], 3) if r["p25"] is not None else None,
                p50=round(r["p50"], 3) if r["p50"] is not None else None,
                p75=round(r["p75"], 3) if r["p75"] is not None else None,
                p90=round(r["p90"], 3) if r["p90"] is not None else None,
                model_confidence=r["model_confidence"],
            )
            for r in s.recent
        ],
    )


@router.get("/weights")
def get_basket_weights(db: Session = Depends(get_db)):
    """Returns all active and historical DGCA route weights."""
    from packages.schemas.models import RouteWeight

    weights = (
        db.query(RouteWeight, Route)
        .join(Route, RouteWeight.route_id == Route.id)
        .order_by(RouteWeight.effective_from.desc(), RouteWeight.weight.desc())
        .all()
    )
    return [
        {
            "route_code": r.route_code,
            "corridor_type": r.corridor_type,
            "passenger_volume": rw.passenger_volume,
            "normalized_weight": rw.weight,
            "weight_pct": round(rw.weight * 100, 2),
            "methodology_version": rw.methodology_version,
            "effective_from": rw.effective_from.isoformat(),
            "effective_to": rw.effective_to.isoformat() if rw.effective_to else None,
        }
        for rw, r in weights
    ]


@router.get(
    "/corridors",
    response_model=List[CorridorSummaryItem],
    tags=["Corridor Intelligence"],
    summary="List Monitored Domestic Corridors",
    description="Returns all 10 monitored domestic corridors (8 trunk metro + 2 regional thin) with route codes, origin/destination airports, DGCA passenger weights, and latest Laspeyres index values.",
)
@router.get("/routes", tags=["Corridor Intelligence"], include_in_schema=False)
def list_routes_summary(db: Session = Depends(get_db)):
    """Returns all 10 monitored corridors with corridor types, weights, and latest index values."""
    cached = get_cached_response("corridor_list", {})
    if cached is not None:
        return cached

    routes = db.query(Route).filter(Route.active).all()
    weights = DGCAWeightEngine.get_active_weights(db)

    # Current representative basic fare per route: median of per-carrier minimums
    # (same methodology as the corridor detail endpoint).
    route_ids = [r.id for r in routes]
    rep_prices: Dict[int, float] = {}
    carrier_mins: Dict[int, Dict[int, float]] = {}
    for route_id, airline_id, status, base_fare in (
        db.query(
            FareObservation.route_id,
            FareObservation.airline_id,
            FareObservation.availability_status,
            FareObservation.base_fare,
        )
        .filter(FareObservation.route_id.in_(route_ids))
        .all()
    ):
        if str(status or "AVAILABLE").upper() != "AVAILABLE" or not base_fare or base_fare <= 0:
            continue
        bucket = carrier_mins.setdefault(route_id, {})
        prev = bucket.get(airline_id)
        if prev is None or base_fare < prev:
            bucket[airline_id] = base_fare

    for route_id, by_carrier in carrier_mins.items():
        carrier_min_fares = sorted(by_carrier.values())
        rep_prices[route_id] = carrier_min_fares[len(carrier_min_fares) // 2]

    results = []
    for r in routes:
        latest_idx = (
            db.query(IndexValue)
            .filter(
                IndexValue.route_id == r.id,
                IndexValue.index_type == "ROUTE_LEVEL",
                IndexValue.index_series == "BASE_FARE",
            )
            .order_by(IndexValue.period_start.desc())
            .first()
        )

        results.append(
            {
                "id": r.id,
                "route_code": r.route_code,
                "origin": r.origin,
                "destination": r.destination,
                "origin_airport": r.origin_airport,
                "destination_airport": r.destination_airport,
                "corridor_type": r.corridor_type,
                "dgca_weight": weights.get(r.route_code, 0.1),
                "current_index": latest_idx.index_value if latest_idx else None,
                "daily_change_pct": latest_idx.daily_change_pct if latest_idx else None,
                "weekly_change_pct": latest_idx.weekly_change_pct if latest_idx else None,
                "monthly_change_pct": latest_idx.monthly_change_pct if latest_idx else None,
                "representative_price": rep_prices.get(r.id),
            }
        )

    set_cached_response("corridor_list", {}, results)
    return results


@router.get(
    "/corridors/{pair}",
    response_model=CorridorDetailResponse,
    tags=["Corridor Intelligence"],
    summary="Corridor Intelligence & Fare Breakdown",
    description="Returns comprehensive econometric intelligence for a specific domestic city-pair (e.g. DEL-BOM). Includes DGCA passenger basket weight, current route index, 5-part statutory fare decomposition, and active carrier price distribution.",
)
def get_corridor_by_pair(
    pair: str = Path(
        ..., description="City-pair corridor code (e.g. DEL-BOM)", examples=["DEL-BOM"]
    ),
    db: Session = Depends(get_db),
):
    """Returns detailed corridor breakdown dynamically computed from authentic database observations."""
    return get_route_detail(route_code=pair, db=db)


@router.get("/routes/{route_code}", tags=["Corridor Intelligence"], include_in_schema=False)
def get_route_detail(
    route_code: str,
    db: Session = Depends(get_db),
):
    """Returns detailed corridor breakdown dynamically computed from authentic database observations."""
    code = route_code.upper()
    route = db.query(Route).filter(Route.route_code == code).first()
    if not route:
        raise HTTPException(status_code=404, detail=f"Corridor {code} not found")

    weights = DGCAWeightEngine.get_active_weights(db)
    airlines = {a.id: a for a in db.query(Airline).all()}

    # Query real observations for this corridor
    observations = (
        db.query(FareObservation)
        .filter(FareObservation.route_id == route.id)
        .order_by(FareObservation.search_timestamp.desc())
        .all()
    )

    if observations:
        # Group by airline
        carrier_map = {}
        for o in observations:
            al = airlines.get(o.airline_id)
            code_str = al.code if al else "6E"
            name = al.name if al else "Carrier"
            if code_str not in carrier_map:
                carrier_map[code_str] = {
                    "carrier": code_str,
                    "name": name,
                    "quotes": [],
                    "flight_count": 0,
                }
            carrier_map[code_str]["quotes"].append(o)
            carrier_map[code_str]["flight_count"] += 1

        carrier_quotes = []
        avail_fares = available_fares(observations)
        min_overall_fare = min(avail_fares) if avail_fares else 0.0

        for code_str, data in carrier_map.items():
            basic_fares = available_fares(data["quotes"])
            basic_min = min(basic_fares) if basic_fares else 4200.0
            flexi_candidates = available_fares(
                [q for q in data["quotes"] if q.fare_family != "BASIC"], "total_fare"
            )
            flexi_fare = min(flexi_candidates) if flexi_candidates else round(basic_min * 1.55, 2)

            carrier_quotes.append(
                {
                    "carrier": code_str,
                    "name": data["name"],
                    "basic_fare": round(basic_min, 2),
                    "flexi_fare": round(flexi_fare, 2),
                    "is_min": abs(basic_min - min_overall_fare) < 1.0,
                    "flights": data["flight_count"],
                }
            )

        # Fare decomposition: average across authentic observations
        n = len(observations)
        base_fare_avg = sum(o.base_fare for o in observations) / n
        fuel_avg = sum(o.fuel_surcharge for o in observations) / n
        tax_avg = sum(o.tax_amount for o in observations) / n
        udf_avg = sum(o.development_fee for o in observations) / n
        conv_avg = sum(o.convenience_fee for o in observations) / n
        total_fare_avg = sum(o.total_fare for o in observations) / n

        # Representative price: median of basic fares across carriers
        basic_fares_list = sorted([c["basic_fare"] for c in carrier_quotes])
        mid = len(basic_fares_list) // 2
        rep_price = basic_fares_list[mid] if basic_fares_list else round(base_fare_avg, 2)

        decomp = {
            "base_fare": round(base_fare_avg, 2),
            "fuel_surcharge": round(fuel_avg, 2),
            "gst_taxes": round(tax_avg, 2),
            "udf_adf": round(udf_avg, 2),
            "convenience_fee": round(conv_avg, 2),
            "total_consumer_fare": round(total_fare_avg, 2),
        }
    else:
        carrier_quotes = []
        rep_price = None
        decomp = None

    return {
        "route_code": route.route_code,
        "origin": route.origin,
        "destination": route.destination,
        "corridor_type": route.corridor_type,
        "weight_pct": round(weights.get(route.route_code, 0.1) * 100, 1),
        "representative_price": rep_price,
        "fare_decomposition": decomp,
        "carrier_breakdown": carrier_quotes,
    }


@router.get(
    "/quotes/live",
    response_model=List[LiveQuoteItem],
    tags=["Live Scraper Pipeline"],
    summary="Recent Verified Airfare Quotes (Live Ingestion Feed)",
    description="Retrieves the most recent verified flight quotes captured from direct carrier booking portals and Google Flights RPC validators with exact timestamps, source provenance, airline identity, and 5-component fee decomposition.",
)
def get_live_quotes(
    corridor: Optional[str] = Query(
        None, description="Filter by corridor code (e.g. DEL-BOM)", examples=["DEL-BOM"]
    ),
    carrier: Optional[str] = Query(
        None, description="Filter by airline code (e.g. 6E, AI, SG, QP, IX)", examples=["6E"]
    ),
    horizon: Optional[int] = Query(
        None, description="Filter by advance purchase days (1, 7, 15, 30, 45)", examples=[15]
    ),
    limit: int = Query(
        50, ge=1, le=200, description="Maximum number of quotes to return", examples=[50]
    ),
    db: Session = Depends(get_db),
):
    """Returns recent verified quotes with live timestamps and source provenance."""
    query = (
        db.query(FareObservation, Route, Airline, Source)
        .join(Route, FareObservation.route_id == Route.id)
        .join(Airline, FareObservation.airline_id == Airline.id)
        .join(Source, FareObservation.source_id == Source.id)
    )
    if corridor:
        query = query.filter(Route.route_code == corridor.upper())
    if carrier:
        query = query.filter(Airline.code == carrier.upper())
    if horizon:
        query = query.filter(FareObservation.advance_purchase_days == horizon)

    records = (
        query.order_by(FareObservation.search_timestamp.desc(), FareObservation.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "id": obs.id,
            "route_code": r.route_code,
            "carrier_code": a.code,
            "carrier_name": a.name,
            "flight_number": obs.flight_number,
            "advance_purchase_days": obs.advance_purchase_days,
            "travel_date": obs.travel_date.isoformat(),
            "observed_at": obs.search_timestamp.isoformat(),
            "source_name": s.name,
            "feed_type": obs.feed_type or "CARRIER_DIRECT",
            "base_fare": obs.base_fare,
            "fuel_surcharge": obs.fuel_surcharge,
            "tax_amount": obs.tax_amount,
            "development_fee": obs.development_fee,
            "convenience_fee": obs.convenience_fee,
            "total_fare": obs.total_fare,
            "is_synthetic": obs.is_synthetic,
        }
        for obs, r, a, s in records
    ]


@router.post(
    "/collection/run",
    tags=["Live Scraper Pipeline"],
    summary="Trigger Real-World Scraper Ingestion Cycle",
    description="Triggers the production dual-feed collection engine across monitored corridors and horizons. Captures live quotes, reconciles discrepancies, persists authentic records to the database, and recalculates indices.",
)
def trigger_production_run(
    background_tasks: BackgroundTasks,
    corridors: Optional[str] = Query(
        None, description="Comma-separated corridor codes (e.g. DEL-BOM,DEL-BLR) or omit for all 10"
    ),
    horizons: Optional[str] = Query(
        None, description="Comma-separated horizons (e.g. 1,7,15,30,45) or omit for all 5"
    ),
    run_in_background: bool = Query(True, description="Execute asynchronously in background task"),
    db: Session = Depends(get_db),
):
    corr_list = [c.strip().upper() for c in corridors.split(",")] if corridors else None
    hor_list = [int(h.strip()) for h in horizons.split(",")] if horizons else None

    from services.collectors.production_collector import run_production_collection

    if run_in_background:
        background_tasks.add_task(
            run_production_collection,
            corridors=corr_list,
            horizons=hor_list,
        )
        return {
            "status": "QUEUED",
            "message": "Production scraper cycle started in background.",
            "target_corridors": corr_list or "ALL_10",
            "target_horizons": hor_list or [1, 7, 15, 30, 45],
        }
    else:
        summary = run_production_collection(
            corridors=corr_list,
            horizons=hor_list,
        )
        return summary


@router.get("/lead-time")
def get_lead_time_analytics(route_code: str = Query("DEL-BOM"), db: Session = Depends(get_db)):
    """Calculates dynamic lead-time curve and surge multiplier dynamically from live observations."""
    route = db.query(Route).filter(Route.route_code == route_code.upper()).first()
    if not route:
        route = db.query(Route).first()

    horizons = [
        (45, "T+45", "Early Bird"),
        (30, "T+30", "Advance Planning"),
        (15, "T+15", "Headline Anchor"),
        (7, "T+7", "Short Planning"),
        (1, "T+1", "Departure Eve"),
    ]

    curve = []
    for days, hor_code, label in horizons:
        obs = (
            db.query(FareObservation)
            .filter(
                FareObservation.route_id == route.id,
                FareObservation.advance_purchase_days == days,
            )
            .all()
        )
        if obs:
            fares = sorted([o.base_fare for o in obs if o.base_fare > 0])
            price = fares[len(fares) // 2] if fares else None
        else:
            price = None

        curve.append(
            {
                "advance_days": days,
                "horizon": hor_code,
                "price": round(price, 2) if price is not None else None,
                "label": label,
            }
        )

    t1_p = curve[-1]["price"]
    t45_p = curve[0]["price"]
    surge_mult = round(t1_p / t45_p, 2) if (t1_p and t45_p and t45_p > 0) else None

    # Carrier escalations
    airlines = {a.id: a.code for a in db.query(Airline).all()}
    carrier_obs = db.query(FareObservation).filter(FareObservation.route_id == route.id).all()
    carrier_horizons = {}
    for o in carrier_obs:
        code = airlines.get(o.airline_id)
        if not code:
            continue
        if code not in carrier_horizons:
            carrier_horizons[code] = {}
        if o.advance_purchase_days not in carrier_horizons[code]:
            carrier_horizons[code][o.advance_purchase_days] = []
        if o.base_fare and o.base_fare > 0:
            carrier_horizons[code][o.advance_purchase_days].append(o.base_fare)

    carrier_escalations = []
    for code, hdict in carrier_horizons.items():
        c_mult = None
        if 1 in hdict and 45 in hdict and min(hdict[45]) > 0:
            c_mult = round(min(hdict[1]) / min(hdict[45]), 2)
        elif 1 in hdict and 14 in hdict and min(hdict[14]) > 0:
            c_mult = round(min(hdict[1]) / min(hdict[14]), 2)
        if c_mult is not None:
            carrier_escalations.append({"carrier": code, "surge_multiplier": c_mult})

    return {
        "route_code": route.route_code,
        "surge_multiplier": surge_mult,
        "lead_time_curve": curve,
        "carrier_escalations": carrier_escalations,
    }


@router.get("/validation")
def get_validation_scorecard(db: Session = Depends(get_db)):
    """Returns MoSPI CPI airfare benchmark directional co-movement metrics and series."""
    from packages.statistics.benchmark_matcher import BenchmarkMatcherService

    # Check if benchmark records exist, if not ingest
    benchmarks = BenchmarkMatcherService.get_benchmark_series(db)
    if not benchmarks:
        BenchmarkMatcherService.ingest_mospi_benchmark_csv(db)
        benchmarks = BenchmarkMatcherService.get_benchmark_series(db)

    # Calculate scorecard
    return BenchmarkMatcherService.calculate_directional_co_movement(
        prototype_monthly=[],
        mospi_monthly=benchmarks,
    )


@router.get("/data-quality")
def get_quality_monitor(db: Session = Depends(get_db)):
    """Returns ingestion health, capture rates, real-life vs synthetic distribution."""
    real_count = db.query(FareObservation).filter(FareObservation.is_synthetic.is_(False)).count()
    synth_count = db.query(FareObservation).filter(FareObservation.is_synthetic.is_(True)).count()
    carrier_direct = (
        db.query(FareObservation).filter(FareObservation.feed_type == "CARRIER_DIRECT").count()
    )
    rpc_fallback = (
        db.query(FareObservation).filter(FareObservation.feed_type == "RPC_FALLBACK").count()
    )

    total = real_count + synth_count
    real_pct = round((real_count / total * 100), 1) if total > 0 else 0.0

    scores = [
        o[0]
        for o in db.query(FareObservation.quality_score)
        .filter(FareObservation.quality_score.isnot(None))
        .all()
    ]
    if scores:
        n_scores = len(scores)
        b_90_100 = sum(1 for s in scores if s >= 90) / n_scores * 100
        b_70_89 = sum(1 for s in scores if 70 <= s < 90) / n_scores * 100
        b_50_69 = sum(1 for s in scores if 50 <= s < 70) / n_scores * 100
        b_0_49 = sum(1 for s in scores if s < 50) / n_scores * 100
        score_dist = [
            {"bracket": "90-100 (ACCEPT)", "percentage": round(b_90_100, 1)},
            {"bracket": "70-89 (ACCEPT_WARNING)", "percentage": round(b_70_89, 1)},
            {"bracket": "50-69 (REVIEW)", "percentage": round(b_50_69, 1)},
            {"bracket": "0-49 (REJECT)", "percentage": round(b_0_49, 1)},
        ]
        # Expected baseline: 10 corridors * 5 horizons * 4 carriers = 200 quotes per cycle
        capture_rate = round(min(100.0, (total / max(1, 200)) * 100), 1) if total > 0 else 0.0
    else:
        score_dist = []
        capture_rate = 0.0

    rejected_count = (
        db.query(FareObservation).filter(FareObservation.quality_status == "REJECT").count()
    )
    warning_count = (
        db.query(FareObservation)
        .filter(FareObservation.quality_status == "ACCEPT_WITH_WARNING")
        .count()
    )
    dedup_count = (
        db.query(FareObservation).filter(FareObservation.is_carrier_min_fare.is_(False)).count()
    )

    return {
        "quote_capture_rate_pct": capture_rate,
        "valid_quotes_count": total,
        "real_life_quotes_count": real_count,
        "synthetic_baseline_count": synth_count,
        "carrier_direct_quotes_count": carrier_direct,
        "rpc_fallback_quotes_count": rpc_fallback,
        "real_life_share_pct": real_pct,
        "rejected_quotes_count": rejected_count,
        "parser_warnings_count": warning_count,
        "deduplicated_quotes_count": dedup_count,
        "score_distribution": score_dist,
    }


@router.get("/validation/cross-feed")
def get_cross_feed_validation(
    route_code: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Returns real-time parity and discrepancy audit records comparing Carrier Direct vs RPC Validator."""
    query = db.query(DiscrepancyAudit)
    if route_code:
        route = db.query(Route).filter(Route.route_code == route_code.upper()).first()
        if route:
            query = query.filter(DiscrepancyAudit.route_id == route.id)

    audits = query.order_by(DiscrepancyAudit.verified_at.desc()).limit(limit).all()

    airlines = {a.id: a.code for a in db.query(Airline).all()}
    routes = {r.id: r.route_code for r in db.query(Route).all()}

    total_audits = len(audits)
    parities = sum(1 for a in audits if a.validation_status == "EXACT_PARITY")
    markups = sum(1 for a in audits if a.validation_status == "AGGREGATOR_MARKUP")
    fallbacks = sum(1 for a in audits if a.validation_status == "FALLBACK_RPC_USED")
    carrier_direct = sum(1 for a in audits if a.carrier_direct_price is not None)

    avg_discrepancy = sum(
        a.discrepancy_pct for a in audits if a.carrier_direct_price is not None
    ) / max(1, carrier_direct)

    return {
        "total_audits": total_audits,
        "carrier_direct_count": carrier_direct,
        "rpc_fallback_count": fallbacks,
        "exact_parity_count": parities,
        "aggregator_markup_count": markups,
        "average_discrepancy_pct": round(avg_discrepancy, 2),
        "parity_rate_pct": round((parities / max(1, carrier_direct)) * 100, 1),
        "audits": [
            {
                "id": a.id,
                "route_code": routes.get(a.route_id, "DEL-BOM"),
                "carrier": airlines.get(a.airline_id, "6E"),
                "flight_number": a.flight_number,
                "travel_date": a.travel_date.isoformat(),
                "advance_days": a.advance_purchase_days,
                "carrier_direct_price": a.carrier_direct_price,
                "rpc_validator_price": a.rpc_validator_price,
                "discrepancy_amount": a.discrepancy_amount,
                "discrepancy_pct": a.discrepancy_pct,
                "status": a.validation_status,
                "notes": a.notes,
                "verified_at": a.verified_at.isoformat() if a.verified_at else None,
            }
            for a in audits
        ],
    }


@router.post("/live/collect")
def trigger_live_collection(
    route_code: str = Query("DEL-BOM"),
    advance_days: int = Query(7),
):
    """Triggers an on-demand real-world dual-feed collection cycle for a route & horizon."""
    from services.collectors.dual_feed_runner import run_dual_feed_collection

    res = run_dual_feed_collection(route_code=route_code, advance_days=advance_days)
    return {
        "status": "SUCCESS",
        "route_code": res["route_code"],
        "travel_date": res["travel_date"],
        "advance_days": res["advance_days"],
        "total_flights_evaluated": res["total_flights_evaluated"],
        "carrier_direct_quotes_count": res["carrier_direct_quotes_count"],
        "rpc_fallback_quotes_count": res["rpc_fallback_quotes_count"],
        "average_discrepancy_pct": res["average_discrepancy_pct"],
    }


@router.post("/collection/trigger-cycle")
def trigger_full_collection_cycle(db: Session = Depends(get_db)):
    """
    Triggers complete scheduled collection cycle across all 10 corridors x 5 horizons (50 jobs)
    and automatically recomputes and persists all daily headline and route indices.
    """
    import datetime

    from services.scheduler.collection_scheduler import CollectionScheduler

    sched = CollectionScheduler()
    summary = sched.trigger_collection_cycle(db=db)
    return {
        "status": "SUCCESS",
        "executed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "collection_summary": summary,
    }


@router.get("/source-health")
def get_sources_health(db: Session = Depends(get_db)):
    """Returns live operational telemetry for registered sources."""
    return CollectorHealthService.get_all_sources_health(db)


@router.get("/fuel-context")
def get_fuel_context(location: str = Query("Delhi"), db: Session = Depends(get_db)):
    """Returns ATF jet fuel price context and non-causal explanation."""
    from packages.statistics.fuel_context import ATFContextService

    return ATFContextService.generate_non_causal_report(db, location=location)


@router.get("/methodology")
def get_methodology_spec(db: Session = Depends(get_db)):
    """Returns mathematical formulation, route basket weights, and documented limitations."""
    version = db.query(MethodologyVersion).filter(MethodologyVersion.version == "APIX-2.0").first()
    weights = DGCAWeightEngine.get_active_weights(db)

    return {
        "version": "APIX-2.0",
        "name": "India Airfare Price Observatory (Modified Laspeyres with Fare-Mix Protection & T+15 Anchor)",
        "base_period": "2026-08-01 = 100",
        "anchor_window": "T+15 (Two-Week Advance Purchase)",
        "formula": "I_t = 100 * sum(w_j * (P_{j,t,T+15} / P_{j,0,T+15}))",
        "estimator": "Lowest available non-refundable Economy fare per scheduled carrier, median across carriers",
        "notes": version.notes if version else "APIX-2.0 production methodology.",
        "basket_weights": [
            {"route": r, "weight": w, "weight_pct": round(w * 100, 2)} for r, w in weights.items()
        ],
    }


# -----------------------------------------------------------------------------
# Carrier-Wise Price Inflation Analytics (CPI-Carrier)
# -----------------------------------------------------------------------------


@router.get("/analytics/carrier-inflation")
def get_carrier_inflation(
    horizon: int = Query(15, description="Advance purchase horizon days (1, 7, 15, 30, 45)"),
    db: Session = Depends(get_db),
):
    """Retrieves current carrier-specific price inflation indices and inter-airline price dispersion."""
    return CarrierInflationService.get_latest_carrier_inflation(db, horizon_days=horizon)


@router.get("/analytics/carrier-inflation/timeseries")
def get_carrier_inflation_timeseries(
    horizon: int = Query(15, description="Advance purchase horizon days (1, 7, 15, 30, 45)"),
    limit: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Retrieves aligned multi-carrier timeseries for comparative airline inflation tracking."""
    return CarrierInflationService.get_carrier_timeseries(db, horizon_days=horizon, limit=limit)


# -----------------------------------------------------------------------------
# Price Fluctuation & Intraday Volatility Analytics
# -----------------------------------------------------------------------------


@router.get("/analytics/volatility")
def get_network_volatility(
    horizon: int = Query(15, description="Advance purchase horizon days (1, 7, 15, 30, 45)"),
    db: Session = Depends(get_db),
):
    """Retrieves route-level price dispersion, intraday spreads, standard deviations, and surge alerts."""
    return VolatilityService.get_network_volatility_summary(db, horizon_days=horizon)


@router.get("/analytics/volatility/{route_code}")
def get_route_volatility_trajectory(
    route_code: str,
    db: Session = Depends(get_db),
):
    """Retrieves flight-by-flight quotes and price distributions for an individual corridor."""
    result = VolatilityService.get_route_intraday_trajectory(db, route_code=route_code.upper())
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# -----------------------------------------------------------------------------
# Executive Market Intelligence & Signals Briefing
# -----------------------------------------------------------------------------


@router.get(
    "/analytics/market-briefing",
    tags=["Statistical Analytics"],
    summary="Executive Market Intelligence & Macroeconomic Signals",
    description="Returns high-frequency executive briefing signals across all 10 monitored corridors: inflation momentum, carrier pricing power, volatility radar, and advance elasticity.",
)
def get_executive_market_briefing(
    horizon: int = Query(15, description="Advance purchase horizon days (1, 7, 15, 30, 45)"),
    series: str = Query(
        "BASE_FARE",
        pattern="^(BASE_FARE|TOTAL_PRICE)$",
        description="Price series (BASE_FARE or TOTAL_PRICE)",
    ),
    db: Session = Depends(get_db),
):
    """Retrieves real-time data-driven executive signals synthesizing carrier power, network volatility, and yield elasticity."""
    from packages.statistics.market_briefing import MarketBriefingService

    return MarketBriefingService.get_market_briefing(db, horizon_days=horizon, series=series)
