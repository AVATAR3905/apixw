"""Representative Route Price Estimators with Fare-Mix Protection."""

from typing import Any, Dict, List, Optional

import numpy as np


def _field_value(obs: Any, field: str) -> Any:
    if isinstance(obs, dict):
        return obs.get(field)
    return getattr(obs, field, None)


def available_fares(observations: List[Any], price_field: str = "base_fare") -> List[float]:
    """Positive fares from AVAILABLE observations (dict or ORM rows).

    Sold-out, cancelled, and zero/missing fares are never priced: a SOLD_OUT
    placeholder row with total_fare=0.0 must not drag MIN/median figures to a
    constant 0 (the fake "fixed price" across routes and days).
    """
    out: List[float] = []
    for obs in observations:
        status = str(_field_value(obs, "availability_status") or "AVAILABLE").upper()
        if status != "AVAILABLE":
            continue
        price = _field_value(obs, price_field)
        if price is None:
            continue
        try:
            price_val = float(price)
        except (ValueError, TypeError):
            continue
        if price_val > 0:
            out.append(price_val)
    return out


FEED_QUALITY_WEIGHTS = {
    "CARRIER_DIRECT": 1.0,
    "RPC_FALLBACK": 0.9,
    "OTA_AGGREGATOR": 0.7,
    "SYNTHETIC_BASELINE": 0.3,
}

FEED_QUALITY_SCORE = {
    "CARRIER_DIRECT": 100,
    "RPC_FALLBACK": 90,
    "OTA_AGGREGATOR": 70,
    "SYNTHETIC_BASELINE": 30,
}

OUTLIER_MAD_THRESHOLD = 3.5
OUTLIER_IQR_MULTIPLIER = 1.5


def _mad_based_outlier_filter(values: np.ndarray, threshold: float = OUTLIER_MAD_THRESHOLD) -> np.ndarray:
    """Median Absolute Deviation based outlier detection."""
    if len(values) < 3:
        return values
    median = np.median(values)
    mad = np.median(np.abs(values - median))
    if mad == 0:
        return values
    z_scores = 0.6745 * (values - median) / mad
    return values[np.abs(z_scores) <= threshold]


def _iqr_based_outlier_filter(values: np.ndarray, multiplier: float = OUTLIER_IQR_MULTIPLIER) -> np.ndarray:
    """IQR-based outlier detection (Tukey's fences)."""
    if len(values) < 4:
        return values
    q1 = np.percentile(values, 25)
    q3 = np.percentile(values, 75)
    iqr = q3 - q1
    if iqr == 0:
        return values
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return values[(values >= lower) & (values <= upper)]


class RepresentativePriceEstimator:
    """Calculates standardized, robust representative route prices per corridor/date/horizon."""

    @classmethod
    def estimate_route_price(
        cls,
        observations: List[Dict[str, Any]],
        price_field: str = "base_fare",
        estimator: str = "MEDIAN",
        cabin_class: str = "ECONOMY",
        fare_family: str = "BASIC",
        apply_waterfall: bool = True,
        apply_outlier_filter: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Estimates representative price with fare-mix protection and waterfall data quality:
        1. Filters to specified cabin and fare family (default: ECONOMY + BASIC).
        2. Filters out SOLD_OUT, CANCELLED, and invalid prices.
        3. Applies waterfall data source prioritization (CARRIER_DIRECT > RPC_FALLBACK > OTA > SYNTHETIC).
        4. Applies outlier detection (MAD + IQR) on per-carrier minimum prices.
        5. For each active carrier, extracts the minimum available quote.
        6. Calculates the estimator (MEDIAN / JEVONS / TRIMMED_MEAN / MEAN) across carriers.
        """
        # Step 1 & 2: Filter valid available observations
        valid_quotes = []
        for obs in observations:
            avail = str(obs.get("availability_status", "AVAILABLE")).upper()
            if avail != "AVAILABLE":
                continue

            obs_cabin = str(obs.get("cabin_class", "ECONOMY")).upper()
            obs_family = str(obs.get("fare_family", "BASIC")).upper()

            if obs_cabin != cabin_class.upper():
                continue
            if fare_family and obs_family != fare_family.upper():
                continue

            price = obs.get(price_field)
            if price is None:
                continue

            try:
                price_val = float(price)
                if price_val > 0:
                    feed_type = str(obs.get("feed_type", "SYNTHETIC_BASELINE")).upper()
                    valid_quotes.append(
                        {
                            "carrier": str(obs.get("carrier", "UNKNOWN")),
                            "price": price_val,
                            "feed_type": feed_type,
                            "feed_quality": FEED_QUALITY_WEIGHTS.get(feed_type, 0.3),
                            "feed_score": FEED_QUALITY_SCORE.get(feed_type, 30),
                        }
                    )
            except (ValueError, TypeError):
                continue

        if not valid_quotes:
            return None

        # Step 3: Waterfall data source prioritization
        if apply_waterfall:
            valid_quotes = cls._apply_waterfall_selection(valid_quotes)

        # Step 3b: Extract minimum price per carrier (fare-mix protection)
        carrier_min_fares: Dict[str, float] = {}
        carrier_feed_info: Dict[str, Dict[str, Any]] = {}
        for q in valid_quotes:
            c = q["carrier"]
            p = q["price"]
            if c not in carrier_min_fares or p < carrier_min_fares[c]:
                carrier_min_fares[c] = p
                carrier_feed_info[c] = {
                    "feed_type": q["feed_type"],
                    "feed_quality": q["feed_quality"],
                    "feed_score": q["feed_score"],
                }

        carrier_prices = list(carrier_min_fares.values())
        if not carrier_prices:
            return None

        carrier_prices_arr = np.array(carrier_prices, dtype=np.float64)

        # Step 4: Outlier detection on carrier minimum prices
        outlier_filtered_prices = carrier_prices_arr
        outlier_info = {"method": "none", "removed_count": 0}
        if apply_outlier_filter and len(carrier_prices_arr) >= 3:
            mad_filtered = _mad_based_outlier_filter(carrier_prices_arr)
            if len(mad_filtered) < len(carrier_prices_arr):
                outlier_filtered_prices = mad_filtered
                outlier_info = {
                    "method": "mad",
                    "removed_count": len(carrier_prices_arr) - len(mad_filtered),
                    "threshold": OUTLIER_MAD_THRESHOLD,
                }
            else:
                iqr_filtered = _iqr_based_outlier_filter(carrier_prices_arr)
                if len(iqr_filtered) < len(carrier_prices_arr):
                    outlier_filtered_prices = iqr_filtered
                    outlier_info = {
                        "method": "iqr",
                        "removed_count": len(carrier_prices_arr) - len(iqr_filtered),
                        "multiplier": OUTLIER_IQR_MULTIPLIER,
                    }

        if len(outlier_filtered_prices) == 0:
            outlier_filtered_prices = carrier_prices_arr
            outlier_info = {"method": "fallback_to_raw", "removed_count": 0}

        # Step 5: Compute representative estimator across carriers
        est_upper = estimator.upper()
        if est_upper == "MEDIAN":
            rep_price = float(np.median(outlier_filtered_prices))
        elif est_upper == "JEVONS":
            rep_price = float(np.exp(np.mean(np.log(outlier_filtered_prices))))
        elif est_upper == "MEAN":
            rep_price = float(np.mean(outlier_filtered_prices))
        elif est_upper == "TRIMMED_MEAN":
            if len(outlier_filtered_prices) >= 5:
                low = np.percentile(outlier_filtered_prices, 10)
                high = np.percentile(outlier_filtered_prices, 90)
                trimmed = outlier_filtered_prices[
                    (outlier_filtered_prices >= low) & (outlier_filtered_prices <= high)
                ]
                rep_price = float(np.mean(trimmed))
            else:
                rep_price = float(np.median(outlier_filtered_prices))
        elif est_upper == "ENSEMBLE":
            # Multi-source ensemble (Phase 5): feed-quality-weighted median of the
            # per-carrier minimum fares. Carrier-direct samples receive full weight,
            # OTA_AGGREGATOR samples are downweighted (0.7) and synthetic baselines
            # heavily discounted (0.3), so the consensus price resists a single
            # low-quality feed while still hearing every platform.
            carrier_codes = list(carrier_min_fares.keys())
            weights = np.array(
                [carrier_feed_info[c]["feed_quality"] for c in carrier_codes],
                dtype=np.float64,
            )
            survivor_vals = set(outlier_filtered_prices.tolist())
            keep = np.array([p in survivor_vals for p in carrier_prices_arr], dtype=bool)
            if keep.sum() > 0:
                ensemble_prices = carrier_prices_arr[keep]
                ensemble_weights = weights[keep]
            else:
                ensemble_prices = carrier_prices_arr
                ensemble_weights = weights
            if len(ensemble_weights) > 0 and ensemble_weights.sum() > 0:
                order = np.argsort(ensemble_prices)
                sorted_prices = ensemble_prices[order]
                sorted_weights = ensemble_weights[order]
                cum = np.cumsum(sorted_weights)
                unit = cum[-1] / 2.0
                crossing = np.searchsorted(cum, unit, side="left")
                rep_price = float(sorted_prices[min(crossing, len(sorted_prices) - 1)])
            else:
                rep_price = float(np.median(ensemble_prices))
        else:
            rep_price = float(np.median(outlier_filtered_prices))

        # Weighted feed quality score across contributing carriers
        contributing_carriers = set(carrier_min_fares.keys()) & set(
            c for c, p in zip(carrier_min_fares.keys(), carrier_prices_arr)
            if p in outlier_filtered_prices or len(carrier_prices_arr) == len(outlier_filtered_prices)
        )
        if contributing_carriers:
            weighted_quality = np.mean([
                carrier_feed_info[c]["feed_score"] for c in contributing_carriers
            ])
            weighted_feed_type = max(
                (carrier_feed_info[c]["feed_type"] for c in contributing_carriers),
                key=lambda ft: FEED_QUALITY_SCORE.get(ft, 0)
            )
        else:
            weighted_quality = 0
            weighted_feed_type = "NONE"

        # Diagnostic statistical metrics
        return {
            "representative_price": round(rep_price, 2),
            "price_field": price_field,
            "estimator": est_upper,
            "carrier_count": len(carrier_min_fares),
            "carrier_count_after_outlier_filter": len(outlier_filtered_prices),
            "total_observations_evaluated": len(valid_quotes),
            "carrier_fares": {c: round(f, 2) for c, f in carrier_min_fares.items()},
            "carrier_feed_quality": carrier_feed_info,
            "min_carrier_price": round(float(np.min(outlier_filtered_prices)), 2),
            "max_carrier_price": round(float(np.max(outlier_filtered_prices)), 2),
            "std_carrier_price": round(float(np.std(outlier_filtered_prices)), 2)
            if len(outlier_filtered_prices) > 1
            else 0.0,
            "p25": round(float(np.percentile(outlier_filtered_prices, 25)), 2),
            "p75": round(float(np.percentile(outlier_filtered_prices, 75)), 2),
            "feed_quality_score": round(weighted_quality, 1),
            "dominant_feed_type": weighted_feed_type,
            "outlier_detection": outlier_info,
        }

    @classmethod
    def _apply_waterfall_selection(cls, quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Waterfall selection: for each carrier, prefer highest quality feed type.
        Priority: CARRIER_DIRECT > RPC_FALLBACK > OTA_AGGREGATOR > SYNTHETIC_BASELINE
        """
        # Group by carrier
        by_carrier: Dict[str, List[Dict[str, Any]]] = {}
        for q in quotes:
            by_carrier.setdefault(q["carrier"], []).append(q)

        selected = []
        for carrier, carrier_quotes in by_carrier.items():
            # Sort by feed quality (descending)
            carrier_quotes.sort(key=lambda x: x["feed_quality"], reverse=True)
            best_quality = carrier_quotes[0]["feed_quality"]
            # Select all quotes at best quality for this carrier
            best_quotes = [q for q in carrier_quotes if q["feed_quality"] == best_quality]
            selected.extend(best_quotes)

        return selected
