"""Ensemble Forecast Engine: TimesFM + LightGBM + Statistical.

Combines multiple models with learned weights for robust probabilistic forecasting.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.seasonal import STL

from database.session import SessionLocal
from packages.schemas.models import IndexValue
from packages.statistics.weights import DGCAWeightEngine
from services.ml.training_pipeline import FeatureEngineer, LightGBMTrainer, get_external_features

logger = logging.getLogger(__name__)

# Default ensemble weights (can be learned via stacking)
DEFAULT_WEIGHTS = {
    "timesfm": 0.50,
    "lightgbm": 0.35,
    "statistical": 0.15,
}


@dataclass
class ForecastPoint:
    """Single forecast point with ensemble prediction intervals."""
    target_date: date
    horizon: int
    p10: float
    p25: float
    p50: float
    p75: float
    p90: float
    model_confidence: float
    component_forecasts: Dict[str, Dict[str, float]]


@dataclass
class EnsembleForecast:
    """Complete ensemble forecast for a series/index_type."""
    series: str
    index_type: str
    forecast_date: date
    horizon_days: int
    points: List[ForecastPoint]
    ensemble_weights: Dict[str, float]
    model_versions: Dict[str, str]
    generated_at: datetime


class StatisticalForecaster:
    """Statistical baseline: STL decomposition + ARIMA/ETS."""

    @staticmethod
    def forecast(
        series: pd.Series,
        horizon: int,
        freq: str = "D",
    ) -> Dict[str, np.ndarray]:
        """
        Generate forecast using STL + ARIMA.

        Returns dict with p10, p50, p90 arrays.
        """
        try:
            # STL decomposition
            stl = STL(series, period=7, robust=True)
            result = stl.fit()

            trend = result.trend
            seasonal = result.seasonal
            resid = result.resid

            # Forecast trend with ARIMA
            trend_model = ARIMA(trend.dropna(), order=(1, 1, 1))
            trend_fit = trend_model.fit()
            trend_fc = trend_fit.forecast(horizon)

            # Forecast seasonal (repeat last cycle)
            seasonal_vals = seasonal.dropna().values
            if len(seasonal_vals) >= 7:
                seasonal_fc = np.tile(seasonal_vals[-7:], horizon // 7 + 1)[:horizon]
            else:
                seasonal_fc = np.zeros(horizon)

            # Residual forecast (assume mean-reverting)
            resid_mean = resid.mean()
            resid_fc = np.full(horizon, resid_mean)

            # Point forecast
            point_fc = trend_fc + seasonal_fc + resid_fc

            # Prediction intervals from residual distribution
            resid_std = resid.std()
            z_90 = 1.645
            z_10 = -1.645

            p10 = point_fc + z_10 * resid_std
            p50 = point_fc
            p90 = point_fc + z_90 * resid_std

            return {
                "p10": p10,
                "p50": p50,
                "p90": p90,
            }

        except Exception as e:
            logger.warning(f"Statistical forecast failed: {e}")
            # Fallback: naive persistence with uncertainty
            last_val = series.iloc[-1]
            return {
                "p10": np.full(horizon, last_val * 0.95),
                "p50": np.full(horizon, last_val),
                "p90": np.full(horizon, last_val * 1.05),
            }


class EnsembleForecaster:
    """Main ensemble forecasting engine."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        timesfm_url: str = "http://localhost:3030",
    ):
        self.weights = weights or DEFAULT_WEIGHTS
        self.timesfm_url = timesfm_url
        self.lgbm_trainer: Optional[LightGBMTrainer] = None
        self.statistical = StatisticalForecaster()
        self._load_lgbm()

    def _load_lgbm(self):
        """Load trained LightGBM models."""
        try:
            from pathlib import Path
            self.lgbm_trainer = LightGBMTrainer.load(Path("models/forecast"))
            logger.info("LightGBM models loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load LightGBM models: {e}")
            self.lgbm_trainer = None

    def _get_timesfm_forecast(
        self,
        history: List[Dict[str, Any]],
        series: str,
        index_type: str,
        horizon: int,
    ) -> Optional[Dict[str, np.ndarray]]:
        """Call TimesFM microservice (optional - falls back gracefully)."""
        import requests

        try:
            payload = {
                "series": series,
                "index_type": index_type,
                "history": history,
                "forecast_horizon": horizon,
                "quantiles": [0.1, 0.5, 0.9],
            }
            response = requests.post(
                f"{self.timesfm_url}/forecast",
                json=payload,
                timeout=30,
            )
            if response.status_code == 200:
                data = response.json()
                points = data.get("points", [])
                return {
                    "p10": np.array([p["p10"] for p in points]),
                    "p50": np.array([p["p50"] for p in points]),
                    "p90": np.array([p["p90"] for p in points]),
                }
        except Exception as e:
            logger.debug(f"TimesFM forecast unavailable: {e}")
        return None

    def _get_lgbm_forecast(
        self,
        history_df: pd.DataFrame,
        series: str,
        index_type: str,
        horizon: int,
    ) -> Optional[Dict[str, np.ndarray]]:
        """Get LightGBM forecast with conformal intervals."""
        if self.lgbm_trainer is None:
            return None

        try:
            # Prepare features for last date
            weights = DGCAWeightEngine.get_active_weights(SessionLocal())
            external = get_external_features(
                SessionLocal(),
                history_df["date"].min(),
                history_df["date"].max(),
            )
            feat_df = FeatureEngineer.create_features(history_df, weights, external)

            # Get prediction for all horizons
            preds = self.lgbm_trainer.predict(feat_df, horizons=list(range(1, horizon + 1)))

            if not preds:
                return None

            # Extract arrays
            p10 = np.array([preds.get(h, {}).get("p10", np.nan) for h in range(1, horizon + 1)])
            p50 = np.array([preds.get(h, {}).get("p50", np.nan) for h in range(1, horizon + 1)])
            p90 = np.array([preds.get(h, {}).get("p90", np.nan) for h in range(1, horizon + 1)])

            return {"p10": p10, "p50": p50, "p90": p90}

        except Exception as e:
            logger.warning(f"LightGBM forecast failed: {e}")
            return None

    def _get_statistical_forecast(
        self,
        series: pd.Series,
        horizon: int,
    ) -> Dict[str, np.ndarray]:
        """Statistical baseline forecast."""
        return self.statistical.forecast(series, horizon)

    def _ensemble_combine(
        self,
        forecasts: Dict[str, Dict[str, np.ndarray]],
        weights: Dict[str, float],
    ) -> Dict[str, np.ndarray]:
        """
        Combine forecasts using weighted quantile averaging.

        For quantiles, we use weighted average of quantile values.
        """
        available = {k: v for k, v in forecasts.items() if v is not None and k in weights}
        if not available:
            raise ValueError("No valid forecasts available")

        # Normalize weights
        total_w = sum(weights[k] for k in available)
        norm_weights = {k: weights[k] / total_w for k in available}

        horizon = len(next(iter(available.values()))["p50"])
        p10 = np.zeros(horizon)
        p50 = np.zeros(horizon)
        p90 = np.zeros(horizon)

        for model_name, fc in available.items():
            w = norm_weights[model_name]
            p10 += w * fc["p10"]
            p50 += w * fc["p50"]
            p90 += w * fc["p90"]

        return {"p10": p10, "p50": p50, "p90": p90}

    def forecast(
        self,
        series: str,
        index_type: str,
        history: List[Dict[str, Any]],
        horizon: int = 28,
        weights: Optional[Dict[str, float]] = None,
    ) -> EnsembleForecast:
        """
        Generate ensemble forecast for next 28 days.

        Args:
            series: BASE_FARE or TOTAL_FARE
            index_type: HEADLINE_T15, SUB_T1, etc.
            history: List of {"date": "YYYY-MM-DD", "value": float}
            horizon: Forecast horizon (1-28 days)
            weights: Custom ensemble weights

        Returns:
            EnsembleForecast with P10/P25/P50/P75/P90 quantiles
        """
        weights = weights or self.weights

        # Convert history to DataFrame
        hist_df = pd.DataFrame(history)
        hist_df["date"] = pd.to_datetime(hist_df["date"])
        hist_df = hist_df.sort_values("date")

        # Get the value series
        values = hist_df["value"].values

        # 1. TimesFM forecast
        timesfm_fc = self._get_timesfm_forecast(history, series, index_type, horizon)

        # 2. LightGBM forecast
        lgbm_fc = self._get_lgbm_forecast(hist_df, series, index_type, horizon)

        # 3. Statistical forecast
        stat_fc = self._get_statistical_forecast(pd.Series(values), horizon)

        # Combine
        forecasts = {
            "timesfm": timesfm_fc,
            "lightgbm": lgbm_fc,
            "statistical": stat_fc,
        }

        ensemble_fc = self._ensemble_combine(forecasts, weights)

        # Build detailed forecast points
        last_date = pd.to_datetime(history[-1]["date"]).date()
        points = []

        for h in range(horizon):
            target_date = last_date + timedelta(days=h + 1)

            # Helper to safely get value at index h from array-like
            def _get_val(arr, idx):
                if arr is None:
                    return None
                if hasattr(arr, 'iloc'):  # pandas Series/DataFrame
                    return float(arr.iloc[idx])
                elif hasattr(arr, '__getitem__'):  # numpy array, list
                    return float(arr[idx])
                else:
                    return float(arr)

            # Component forecasts for this horizon
            components = {}
            for model_name, fc in forecasts.items():
                if fc is not None:
                    components[model_name] = {
                        "p10": _get_val(fc.get("p10"), h),
                        "p50": _get_val(fc.get("p50"), h),
                        "p90": _get_val(fc.get("p90"), h),
                    }

            # Ensemble prediction intervals
            p10 = _get_val(ensemble_fc.get("p10"), h)
            p50 = _get_val(ensemble_fc.get("p50"), h)
            p90 = _get_val(ensemble_fc.get("p90"), h)

            if p10 is None or p50 is None or p90 is None:
                continue  # Skip if ensemble failed

            # Additional quantiles (interpolated)
            p25 = p10 + 0.33 * (p50 - p10)
            p75 = p50 + 0.33 * (p90 - p50)

            # Model confidence from ensemble agreement
            point_preds = []
            for fc in forecasts.values():
                if fc is not None:
                    val = _get_val(fc.get("p50"), h)
                    if val is not None:
                        point_preds.append(val)

            if len(point_preds) > 1:
                pred_std = np.std(point_preds)
                pred_mean = np.mean(point_preds)
                rel_std = pred_std / max(abs(pred_mean), 1.0)
                confidence = max(0.1, min(1.0, 1.0 - rel_std))
            else:
                confidence = 0.5

            points.append(ForecastPoint(
                target_date=target_date,
                horizon=h + 1,
                p10=round(p10, 2),
                p25=round(p25, 2),
                p50=round(p50, 2),
                p75=round(p75, 2),
                p90=round(p90, 2),
                model_confidence=round(confidence, 3),
                component_forecasts=components,
            ))

        return EnsembleForecast(
            series=series,
            index_type=index_type,
            forecast_date=date.today(),
            horizon_days=horizon,
            points=points,
            ensemble_weights=weights,
            model_versions={
                "timesfm": "timesfm-2.5-500m-jax",
                "lightgbm": "lgbm-v3-conformal",
                "statistical": "stl-arima-v1",
            },
            generated_at=datetime.utcnow(),
        )

    def forecast_all_series(
        self,
        history_by_series: Dict[str, Dict[str, List[Dict[str, Any]]]],
        horizon: int = 28,
    ) -> Dict[str, Dict[str, EnsembleForecast]]:
        """
        Generate forecasts for all series/index_type combinations.

        Args:
            history_by_series: {series: {index_type: history}}
            horizon: Forecast horizon

        Returns:
            Nested dict: {series: {index_type: EnsembleForecast}}
        """
        results = {}
        for series, idx_types in history_by_series.items():
            results[series] = {}
            for index_type, history in idx_types.items():
                if len(history) >= 10:  # Minimum history
                    results[series][index_type] = self.forecast(
                        series, index_type, history, horizon
                    )
        return results


def get_historical_index_data(
    db: SessionLocal,
    series: str = "BASE_FARE",
    index_type: str = "HEADLINE_T15",
    days: int = 100,
) -> List[Dict[str, Any]]:
    """Fetch historical index data for forecasting."""
    records = db.query(IndexValue).filter(
        IndexValue.index_series == series,
        IndexValue.index_type == index_type,
        IndexValue.route_id.is_(None),
    ).order_by(IndexValue.period_start.desc()).limit(days).all()

    return [
        {"date": r.period_start.isoformat(), "value": float(r.index_value)}
        for r in reversed(records)
    ]


def get_all_historical_data(db: SessionLocal, days: int = 100) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Fetch historical data for all series/index_type combinations."""
    series_list = ["BASE_FARE", "TOTAL_FARE"]
    index_types = ["HEADLINE_T15", "SUB_T1", "SUB_T7", "SUB_T30", "SUB_T45"]

    result = {}
    for series in series_list:
        result[series] = {}
        for idx_type in index_types:
            result[series][idx_type] = get_historical_index_data(db, series, idx_type, days)
    return result
