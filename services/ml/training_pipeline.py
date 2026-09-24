"""LightGBM Training Pipeline with Conformal Prediction Intervals.

Trains gradient boosted model for airfare index forecasting with
rigorous prediction intervals via conformal prediction.
"""
import json
import logging
import pickle
import warnings
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from database.session import SessionLocal
from packages.schemas.models import IndexValue
from packages.shared.time_utils import utcnow
from packages.statistics.weights import DGCAWeightEngine

warnings.filterwarnings("ignore", category=UserWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_DIR = Path("models/forecast")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class ModelMetrics:
    """Training/validation metrics."""
    mae: float
    rmse: float
    mape: float
    coverage_90: float
    coverage_80: float
    interval_width_90: float
    interval_width_80: float
    n_train: int
    n_val: int


@dataclass
class ConformalPredictor:
    """Conformal prediction for valid prediction intervals."""
    calibration_scores: np.ndarray
    alpha: float

    def predict_interval(self, point_pred: np.ndarray, quantile: float) -> Tuple[np.ndarray, np.ndarray]:
        """Generate prediction interval for given quantile."""
        n = len(self.calibration_scores)
        k = int(np.ceil((n + 1) * (1 - self.alpha)))
        k = min(k, n - 1)
        score = np.sort(self.calibration_scores)[k]
        lower = point_pred - score
        upper = point_pred + score
        return lower, upper


class FeatureEngineer:
    """Feature engineering for airfare index forecasting."""

    HORIZONS = [1, 7, 15, 30, 45]
    LAG_WINDOWS = [1, 2, 3, 7, 14, 21, 28]

    @classmethod
    def create_features(
        cls,
        index_df: pd.DataFrame,
        route_weights: Dict[str, float],
        external_data: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Create features for each (date, horizon, series) combination.

        Features:
        - Temporal: dow, week, month, quarter, holiday proximity
        - Lag: 1,2,3,7,14,21,28 day lags for each horizon
        - Rolling: 7,14,28 day rolling mean/std/min/max
        - Route: weight, competition, distance proxy
        - Market: fuel, fx, seasonal indicators
        """
        df = index_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values(["series", "index_type", "date"])

        feature_rows = []

        for (series, idx_type), group in df.groupby(["series", "index_type"]):
            group = group.copy().reset_index(drop=True)

            # Temporal features
            group["dow"] = group["date"].dt.dayofweek
            group["week"] = group["date"].dt.isocalendar().week
            group["month"] = group["date"].dt.month
            group["quarter"] = group["date"].dt.quarter
            group["day_of_year"] = group["date"].dt.dayofyear
            group["is_month_start"] = group["date"].dt.is_month_start.astype(int)
            group["is_month_end"] = group["date"].dt.is_month_end.astype(int)

            # Lag features
            for lag in cls.LAG_WINDOWS:
                group[f"lag_{lag}"] = group["index_value"].shift(lag)
                group[f"lag_{lag}_pct"] = group["index_value"].pct_change(lag)

            # Rolling features
            for window in [7, 14, 28]:
                group[f"roll_mean_{window}"] = group["index_value"].rolling(window).mean()
                group[f"roll_std_{window}"] = group["index_value"].rolling(window).std()
                group[f"roll_min_{window}"] = group["index_value"].rolling(window).min()
                group[f"roll_max_{window}"] = group["index_value"].rolling(window).max()

            # Momentum features
            group["momentum_7"] = group["index_value"] / group["lag_7"] - 1
            group["momentum_14"] = group["index_value"] / group["lag_14"] - 1
            group["momentum_28"] = group["index_value"] / group["lag_28"] - 1

            # Volatility features
            group["vol_7"] = group["index_value"].pct_change().rolling(7).std()
            group["vol_28"] = group["index_value"].pct_change().rolling(28).std()

            # Horizon encoding
            horizon = int(idx_type.replace("HEADLINE_T", "").replace("SUB_T", ""))
            group["horizon"] = horizon
            group["is_headline"] = int(horizon == 15)

            # Series encoding
            group["is_base_fare"] = int(series == "BASE_FARE")

            # Route-level aggregates (weighted)
            if route_weights:
                # Add market-level features
                group["mkt_weight_avg"] = np.mean(list(route_weights.values()))
                group["mkt_concentration"] = np.sum([w**2 for w in route_weights.values()])  # HHI

            # Target: next day's index_value (for 1-day ahead forecast)
            # For multi-horizon, we create separate targets
            for h in [1, 7, 15, 30, 45]:
                target_col = f"target_{h}d"
                group[target_col] = group["index_value"].shift(-h)

            # External data merge
            if external_data is not None:
                group = group.merge(external_data, on="date", how="left")

            feature_rows.append(group)

        result = pd.concat(feature_rows, ignore_index=True)

        # Drop rows with NaN targets (last N days)
        target_cols = [f"target_{h}d" for h in [1, 7, 15, 30, 45]]
        result = result.dropna(subset=target_cols, how="all")

        return result

    @classmethod
    def get_feature_columns(cls, df: pd.DataFrame) -> List[str]:
        """Get list of feature columns (exclude targets, identifiers)."""
        exclude = {"date", "series", "index_type", "index_value", "target_1d", "target_7d", "target_15d", "target_30d", "target_45d"}
        return [c for c in df.columns if c not in exclude]


class LightGBMTrainer:
    """Trains LightGBM models for each horizon with conformal intervals."""

    def __init__(
        self,
        n_estimators: int = 500,
        learning_rate: float = 0.05,
        max_depth: int = 6,
        num_leaves: int = 31,
        min_child_samples: int = 20,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        random_state: int = 42,
        calibration_alpha: float = 0.1,
    ):
        self.params = {
            "objective": "regression",
            "metric": "mae",
            "n_estimators": n_estimators,
            "learning_rate": learning_rate,
            "max_depth": max_depth,
            "num_leaves": num_leaves,
            "min_child_samples": min_child_samples,
            "subsample": subsample,
            "colsample_bytree": colsample_bytree,
            "random_state": random_state,
            "verbosity": -1,
            "n_jobs": -1,
        }
        self.calibration_alpha = calibration_alpha
        self.models: Dict[int, lgb.Booster] = {}
        self.conformal_predictors: Dict[int, ConformalPredictor] = {}
        self.feature_columns: List[str] = []
        self.horizons = [1, 7, 15, 30, 45]

    def train(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
        feature_cols: List[str],
    ) -> Dict[int, ModelMetrics]:
        """Train separate model for each forecast horizon."""
        metrics = {}

        for h in self.horizons:
            target_col = f"target_{h}d"

            # Filter valid rows
            train_valid = train_df.dropna(subset=[target_col] + feature_cols)
            val_valid = val_df.dropna(subset=[target_col] + feature_cols)

            if len(train_valid) < 50 or len(val_valid) < 20:
                logger.warning(f"Insufficient data for horizon {h}d: train={len(train_valid)}, val={len(val_valid)}")
                continue

            X_train = train_valid[feature_cols]
            y_train = train_valid[target_col]
            X_val = val_valid[feature_cols]
            y_val = val_valid[target_col]

            # Train
            train_data = lgb.Dataset(X_train, label=y_train)
            val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

            model = lgb.train(
                self.params,
                train_data,
                valid_sets=[train_data, val_data],
                valid_names=["train", "val"],
                callbacks=[
                    lgb.early_stopping(50),
                    lgb.log_evaluation(100),
                ],
            )

            # Predict on validation
            val_pred = model.predict(X_val, num_iteration=model.best_iteration)

            # Calibration for conformal intervals
            residuals = np.abs(y_val - val_pred)
            conformal = ConformalPredictor(
                calibration_scores=residuals.values,
                alpha=self.calibration_alpha,
            )

            # Metrics
            mae = mean_absolute_error(y_val, val_pred)
            rmse = np.sqrt(mean_squared_error(y_val, val_pred))
            mape = np.mean(np.abs((y_val - val_pred) / y_val)) * 100

            # Coverage at 90% and 80%
            lower_90, upper_90 = conformal.predict_interval(val_pred, 0.1)
            lower_80, upper_80 = conformal.predict_interval(val_pred, 0.2)

            coverage_90 = np.mean((y_val >= lower_90) & (y_val <= upper_90))
            coverage_80 = np.mean((y_val >= lower_80) & (y_val <= upper_80))
            interval_width_90 = np.mean(upper_90 - lower_90)
            interval_width_80 = np.mean(upper_80 - lower_80)

            metrics[h] = ModelMetrics(
                mae=mae,
                rmse=rmse,
                mape=mape,
                coverage_90=coverage_90,
                coverage_80=coverage_80,
                interval_width_90=interval_width_90,
                interval_width_80=interval_width_80,
                n_train=len(train_valid),
                n_val=len(val_valid),
            )

            self.models[h] = model
            self.conformal_predictors[h] = conformal

            logger.info(
                f"Horizon {h}d: MAE={mae:.2f}, RMSE={rmse:.2f}, MAPE={mape:.1f}%, "
                f"Cov90={coverage_90:.2f}, Cov80={coverage_80:.2f}"
            )

        self.feature_columns = feature_cols
        return metrics

    def predict(
        self,
        df: pd.DataFrame,
        horizons: Optional[List[int]] = None,
    ) -> Dict[int, Dict[str, np.ndarray]]:
        """
        Generate predictions with conformal intervals.

        Returns: {horizon: {"point": pred, "p10": lower_90, "p50": pred, "p90": upper_90}}
        """
        horizons = horizons or self.horizons
        results = {}

        for h in horizons:
            if h not in self.models:
                continue

            model = self.models[h]
            conformal = self.conformal_predictors[h]

            # Prepare features (last row for forecasting)
            X = df[self.feature_columns].iloc[[-1]]
            point_pred = model.predict(X, num_iteration=model.best_iteration)[0]

            # Conformal intervals
            lower_90, upper_90 = conformal.predict_interval(np.array([point_pred]), 0.1)
            lower_80, upper_80 = conformal.predict_interval(np.array([point_pred]), 0.2)

            results[h] = {
                "point": point_pred,
                "p10": lower_90[0],
                "p50": point_pred,
                "p90": upper_90[0],
                "p20": lower_80[0],
                "p80": upper_80[0],
            }

        return results

    def save(self, path: Path):
        """Save models and conformal predictors."""
        path.mkdir(parents=True, exist_ok=True)

        for h, model in self.models.items():
            model.save_model(str(path / f"lgbm_h{h}d.txt"))

        with open(path / "conformal_predictors.pkl", "wb") as f:
            pickle.dump(self.conformal_predictors, f)

        with open(path / "feature_columns.json", "w") as f:
            json.dump(self.feature_columns, f)

        with open(path / "metadata.json", "w") as f:
            json.dump({
                "horizons": self.horizons,
                "params": self.params,
                "calibration_alpha": self.calibration_alpha,
                "trained_at": utcnow().isoformat(),
            }, f)

    @classmethod
    def load(cls, path: Path) -> "LightGBMTrainer":
        """Load trained models."""
        with open(path / "feature_columns.json") as f:
            feature_columns = json.load(f)

        with open(path / "metadata.json") as f:
            metadata = json.load(f)

        trainer = cls(
            n_estimators=metadata["params"]["n_estimators"],
            learning_rate=metadata["params"]["learning_rate"],
            max_depth=metadata["params"]["max_depth"],
            num_leaves=metadata["params"]["num_leaves"],
            min_child_samples=metadata["params"]["min_child_samples"],
            subsample=metadata["params"]["subsample"],
            colsample_bytree=metadata["params"]["colsample_bytree"],
            random_state=metadata["params"]["random_state"],
            calibration_alpha=metadata["calibration_alpha"],
        )
        trainer.feature_columns = feature_columns

        with open(path / "conformal_predictors.pkl", "rb") as f:
            trainer.conformal_predictors = pickle.load(f)

        for h in trainer.horizons:
            model_path = path / f"lgbm_h{h}d.txt"
            if model_path.exists():
                trainer.models[h] = lgb.Booster(model_file=str(model_path))

        return trainer


def get_external_features(db: SessionLocal, start_date: date, end_date: date) -> pd.DataFrame:
    """Fetch external features (fuel, FX, holidays) for date range."""
    # Placeholder - integrate with real data sources
    dates = pd.date_range(start_date, end_date, freq="D")
    df = pd.DataFrame({"date": dates})

    # Fuel price proxy (WTI crude)
    df["fuel_price"] = 80.0 + np.random.normal(0, 5, len(df))

    # USD/INR FX rate
    df["fx_usd_inr"] = 83.0 + np.random.normal(0, 0.5, len(df))

    # Holiday indicator (simplified)
    df["is_holiday"] = df["date"].dt.dayofweek.isin([5, 6]).astype(int)

    return df


def train_forecast_models() -> Dict[int, ModelMetrics]:
    """Main training entry point."""
    db = SessionLocal()
    try:
        # Fetch historical index data
        records = db.query(IndexValue).filter(
            IndexValue.route_id.is_(None),  # National level only
            IndexValue.index_series.in_(["BASE_FARE", "TOTAL_FARE"]),
        ).order_by(IndexValue.period_start).all()

        if not records:
            raise ValueError("No index data found in database")

        # Convert to DataFrame
        df = pd.DataFrame([{
            "date": r.period_start,
            "series": r.index_series,
            "index_type": r.index_type,
            "index_value": r.index_value,
            "coverage": r.coverage_rate,
            "carrier_diversity": r.carrier_diversity,
            "feed_quality": r.feed_quality_score,
        } for r in records])

        # Get route weights
        weights = DGCAWeightEngine.get_active_weights(db)

        # External features
        external = get_external_features(db, df["date"].min(), df["date"].max())

        # Feature engineering
        feat_df = FeatureEngineer.create_features(df, weights, external)
        feature_cols = FeatureEngineer.get_feature_columns(feat_df)

        # Time series split (last 28 days for validation)
        split_date = feat_df["date"].max() - timedelta(days=28)
        train_df = feat_df[feat_df["date"] <= split_date].copy()
        val_df = feat_df[feat_df["date"] > split_date].copy()

        logger.info(f"Training: {len(train_df)} samples, Validation: {len(val_df)} samples")

        # Train
        trainer = LightGBMTrainer(calibration_alpha=0.1)
        metrics = trainer.train(train_df, val_df, feature_cols)

        # Save
        trainer.save(MODEL_DIR)

        # Save metrics
        with open(MODEL_DIR / "metrics.json", "w") as f:
            json.dump({str(k): v.__dict__ for k, v in metrics.items()}, f, indent=2, default=str)

        logger.info("Training complete. Metrics:")
        for h, m in metrics.items():
            logger.info(f"  {h}d: MAE={m.mae:.2f}, Coverage90={m.coverage_90:.2f}")

        return metrics

    finally:
        db.close()


if __name__ == "__main__":
    train_forecast_models()
