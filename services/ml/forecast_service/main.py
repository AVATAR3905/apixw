"""TimesFM 2.5 Forecast Microservice (Port 3030).

Google Research's 200M-parameter time-series foundation model for zero-shot forecasting.
Runs as standalone HTTP service for the APIX ensemble.
"""
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

import numpy as np
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from packages.shared.time_utils import utcnow

# TimesFM import (lazy-loaded to avoid startup issues)
_timesfm_model = None


def get_timesfm_model():
    """Lazy-load TimesFM model."""
    global _timesfm_model
    if _timesfm_model is None:
        try:
            import timesfm
            _timesfm_model = timesfm.TimesFm(
                hparams=timesfm.TimesFmHparams(
                    backend="jax",
                    per_core_batch_size=32,
                    horizon_len=28,
                    input_patch_len=32,
                    output_patch_len=128,
                    num_layers=20,
                    model_dims=1280,
                ),
                checkpoint=timesfm.TimesFmCheckpoint(
                    huggingface_repo_id="google/timesfm-2.0-500m-jax",
                ),
            )
            logging.info("TimesFM model loaded successfully")
        except Exception as e:
            logging.error(f"Failed to load TimesFM: {e}")
            raise
    return _timesfm_model


@dataclass
class ForecastResult:
    """Single forecast point with prediction intervals."""
    target_date: date
    horizon: int
    p10: float
    p50: float
    p90: float
    model_confidence: float


class ForecastRequest(BaseModel):
    """Request for index forecasting."""
    series: str = Field("BASE_FARE", pattern="^(BASE_FARE|TOTAL_FARE)$")
    index_type: str = Field("HEADLINE_T15", pattern="^(HEADLINE_T15|SUB_T1|SUB_T7|SUB_T15|SUB_T30|SUB_T45)$")
    history: List[Dict[str, Any]] = Field(..., min_length=10, max_length=100)
    forecast_horizon: int = Field(28, ge=1, le=28)
    quantiles: List[float] = Field([0.1, 0.5, 0.9])


class ForecastPoint(BaseModel):
    """Single forecast point response."""
    target_date: str
    horizon: int
    p10: float
    p50: float
    p90: float
    model_confidence: float
    model_version: str


class ForecastResponse(BaseModel):
    """Forecast response with metadata."""
    series: str
    index_type: str
    forecast_date: str
    horizon_days: int
    points: List[ForecastPoint]
    model_version: str
    ensemble_weights: Dict[str, float]
    generated_at: str


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    version: str


app = FastAPI(
    title="APIX TimesFM Forecast Service",
    description="Google TimesFM 2.5 zero-shot forecasting for airfare indices",
    version="1.0.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    model_loaded = _timesfm_model is not None
    return HealthResponse(
        status="healthy" if model_loaded else "degraded",
        model_loaded=model_loaded,
        version="timesfm-2.5-500m",
    )


@app.post("/forecast", response_model=ForecastResponse)
async def forecast(request: ForecastRequest):
    """
    Generate probabilistic forecast using TimesFM 2.5.

    Expects history as list of {"date": "YYYY-MM-DD", "value": float}.
    Returns P10/P50/P90 quantiles for next 28 days.
    """
    try:
        model = get_timesfm_model()

        # Prepare input sequence
        dates = [datetime.fromisoformat(h["date"]).date() for h in request.history]
        values = [float(h["value"]) for h in request.history]

        # TimesFM expects: (batch, seq_len) - we use last 512 points max
        context_len = min(len(values), 512)
        context = np.array([values[-context_len:]], dtype=np.float32)

        # Generate forecast
        forecast_horizon = request.forecast_horizon
        quantiles = request.quantiles

        # TimesFM forecast
        point_forecast, quantile_forecast = model.forecast(
            context,
            horizon=forecast_horizon,
            quantiles=quantiles,
        )

        # point_forecast shape: (1, horizon)
        # quantile_forecast shape: (1, horizon, n_quantiles)
        point_vals = point_forecast[0]
        quantile_vals = quantile_forecast[0]  # (horizon, n_quantiles)

        # Map quantiles to P10/P50/P90
        quantile_map = {q: i for i, q in enumerate(quantiles)}
        p10_idx = quantile_map.get(0.1, 0)
        quantile_map.get(0.5, 1 if len(quantiles) > 1 else 0)
        p90_idx = quantile_map.get(0.9, 2 if len(quantiles) > 2 else -1)

        # Build response points
        last_date = dates[-1]
        points = []
        for h in range(forecast_horizon):
            target_date = last_date + timedelta(days=h + 1)
            p10 = float(quantile_vals[h, p10_idx])
            p50 = float(point_vals[h])  # Point forecast is median
            p90 = float(quantile_vals[h, p90_idx])

            # Model confidence based on prediction interval width
            interval_width = p90 - p10
            relative_width = interval_width / max(abs(p50), 1.0)
            confidence = max(0.1, min(1.0, 1.0 - relative_width))

            points.append(ForecastPoint(
                target_date=target_date.isoformat(),
                horizon=h + 1,
                p10=round(p10, 2),
                p50=round(p50, 2),
                p90=round(p90, 2),
                model_confidence=round(confidence, 3),
                model_version="timesfm-2.5-500m-jax",
            ))

        response = ForecastResponse(
            series=request.series,
            index_type=request.index_type,
            forecast_date=date.today().isoformat(),
            horizon_days=forecast_horizon,
            points=points,
            model_version="timesfm-2.5-500m-jax",
            ensemble_weights={"timesfm": 1.0},
            generated_at=utcnow().isoformat() + "Z",
        )

        logger.info(f"Generated forecast: {request.series}/{request.index_type} for {forecast_horizon} days")
        return response

    except Exception as e:
        logger.error(f"Forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/forecast/ensemble")
async def forecast_ensemble(request: ForecastRequest):
    """
    Ensemble forecast combining TimesFM + LightGBM + Statistical.
    Falls back to TimesFM-only if other models unavailable.
    """
    # For now, delegate to single model
    # Full ensemble implemented in services/ml/ensemble.py
    return await forecast(request)


if __name__ == "__main__":
    port = int(os.getenv("FORECAST_PORT", "3030"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
