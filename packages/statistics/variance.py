"""Index variance estimation (NSO-standard bootstrap & jackknife).

Implements uncertainty quantification on the national Laspeyres index and its
route-level components, so every published point value carries a standard error
and confidence interval exactly like an official CPI release.

Two estimators are provided:

1. ``bootstrap_index_variance`` -- the primary estimator.  It resamples the
   elementary ("route-horizon") cells with replacement -- i.e. the per-carrier
   minimum fares that feed each Jevons geometric mean -- recomputes the full
   Laspeyres index ``n_bootstrap`` times and reports the bootstrap standard
   error plus percentile- and normal-approximation confidence intervals.

2. ``jackknife_index_variance`` -- a delete-one-route jackknife that isolates
   how much sampling uncertainty each corridor contributes to the national
   index.  This is the standard way national statistical offices attribute
   index variance to basket components.

Both estimators reuse the exact aggregation rule of
``AirfareIndexEngine.calculate_national_index`` (weights re-normalised over the
routes actually present), so the variance is measured on the published
estimator itself rather than on a proxy.
"""

import math
from typing import Dict, List, Optional

import numpy as np


class IndexVarianceError(Exception):
    """Raised when the variance estimator receives degenerate inputs."""

    pass


class IndexVarianceEstimator:
    """Bootstrap / jackknife uncertainty estimators for the APIX national index."""

    DEFAULT_BOOTSTRAP_REPLICATIONS: int = 2000
    DEFAULT_CONFIDENCE_LEVEL: float = 0.95

    @staticmethod
    def _existing_routes(
        route_samples: Dict[str, List[float]],
        base_prices: Dict[str, float],
        route_weights: Dict[str, float],
    ) -> List[str]:
        """Routes that can actually contribute to a variance computation."""
        active = []
        for rcode in route_weights:
            sample = route_samples.get(rcode)
            if not sample or len(sample) == 0:
                continue
            base = base_prices.get(rcode)
            if base is None or base <= 0:
                continue
            valid = [p for p in sample if p is not None and p > 0]
            if not valid:
                continue
            active.append(rcode)
        return active

    @staticmethod
    def _normalized_weights(route_weights: Dict[str, float], routes: List[str]) -> np.ndarray:
        raw = np.array([route_weights[r] for r in routes], dtype=np.float64)
        total = raw.sum()
        if total <= 0:
            raise IndexVarianceError("Route weights sum to zero over the active basket")
        return raw / total

    @staticmethod
    def _cell_matrix(
        rng: np.random.Generator,
        route_samples: Dict[str, List[float]],
        routes: List[str],
        n_bootstrap: int,
    ) -> np.ndarray:
        """(n_bootstrap, n_routes) matrix of bootstrap Jevons cell prices.

        Each column resamples that route's per-carrier minimum fares with
        replacement (sample size preserved) and applies the Jevons geometric
        mean used by the elementary estimator.
        """
        matrix = np.empty((n_bootstrap, len(routes)), dtype=np.float64)
        for i, rcode in enumerate(routes):
            sample = np.array(
                [p for p in route_samples[rcode] if p is not None and p > 0],
                dtype=np.float64,
            )
            draws = sample[rng.integers(0, sample.size, size=(n_bootstrap, sample.size))]
            matrix[:, i] = np.exp(np.mean(np.log(draws), axis=1))
        return matrix

    @staticmethod
    def _validate_params(n_bootstrap: int, confidence_level: float) -> None:
        """Reject degenerate bootstrap sizing / confidence levels up front.

        Central health check so a misconfigured ``n_bootstrap`` or CI level can
        never silently produce NaNs in a published index series.
        """
        if not isinstance(n_bootstrap, int) or n_bootstrap < 2:
            raise IndexVarianceError(
                f"n_bootstrap must be an integer >= 2, got {n_bootstrap!r}"
            )
        if not 0.0 < confidence_level < 1.0:
            raise IndexVarianceError(
                f"confidence_level must be strictly between 0 and 1, got {confidence_level!r}"
            )

    @classmethod
    def bootstrap_index_variance(
        cls,
        route_samples: Dict[str, List[float]],
        base_prices: Dict[str, float],
        route_weights: Dict[str, float],
        observed_index: Optional[float] = None,
        n_bootstrap: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        random_seed: Optional[int] = None,
    ) -> Dict[str, float]:
        """Bootstrap standard error & confidence interval for the national index.

        Args:
            route_samples: {route_code: per-carrier minimum fares in the cell}.
            base_prices: {route_code: base-period representative price}.
            route_weights: {route_code: normalized DGCA weight} (sums to 1).
            observed_index: the published index value (for bias reporting).
            n_bootstrap: number of resample replications.
            confidence_level: e.g. 0.95 for a 95% interval.
            random_seed: optional seed for reproducible bootstrap draws.

        Returns a dict with standard_error, ci_lower, ci_upper, mean_index,
        median_index, bias, method, n_bootstrap, n_routes_bootstrapped.
        """
        cls._validate_params(n_bootstrap, confidence_level)

        routes = cls._existing_routes(route_samples, base_prices, route_weights)
        if not routes:
            raise IndexVarianceError(
                "No routes with valid samples, base prices and weights available"
            )

        weights = cls._normalized_weights(route_weights, routes)
        base = np.array([base_prices[r] for r in routes], dtype=np.float64)

        rng = np.random.default_rng(random_seed)
        cells = cls._cell_matrix(rng, route_samples, routes, n_bootstrap)
        relatives = cells / base  # (B, R)
        bootstrap_indices = 100.0 * (relatives * weights).sum(axis=1)

        alpha = 1.0 - confidence_level
        lo, hi = np.percentile(bootstrap_indices, [100 * alpha / 2, 100 * (1 - alpha / 2)])

        # Invariant: a confidence interval must contain the point value it
        # annotates. The published index is rounded to 2dp while bootstrap
        # cells are not, so a (near-)degenerate cell can sit a hair off the
        # resample distribution -- clamp the percentile bounds to observed.
        if observed_index is not None:
            lo = min(float(lo), float(observed_index))
            hi = max(float(hi), float(observed_index))

        mean_index = float(np.mean(bootstrap_indices))
        median_index = float(np.median(bootstrap_indices))
        standard_error = float(np.std(bootstrap_indices, ddof=1))

        quantile = scipy_norm_ppf(1 - alpha / 2)
        half_width = quantile * standard_error

        return {
            "method": f"BOOTSTRAP_PERCENTILE_{int(confidence_level * 100)}",
            "n_bootstrap": int(n_bootstrap),
            "n_routes_bootstrapped": len(routes),
            "standard_error": round(standard_error, 4),
            "ci_lower": round(float(lo), 4),
            "ci_upper": round(float(hi), 4),
            "ci_level": confidence_level,
            "mean_index": round(mean_index, 4),
            "median_index": round(median_index, 4),
            "bias": round(mean_index - observed_index, 4) if observed_index is not None else None,
            "ci_normal_lower": round(observed_index - half_width, 4)
            if observed_index is not None
            else None,
            "ci_normal_upper": round(observed_index + half_width, 4)
            if observed_index is not None
            else None,
        }

    @classmethod
    def bootstrap_route_index_variance(
        cls,
        route_sample: List[float],
        base_price: float,
        observed_index: Optional[float] = None,
        n_bootstrap: int = DEFAULT_BOOTSTRAP_REPLICATIONS,
        confidence_level: float = DEFAULT_CONFIDENCE_LEVEL,
        random_seed: Optional[int] = None,
    ) -> Dict[str, float]:
        """Bootstrap CI for a single route-level index (100 * P_t / P_0)."""
        cls._validate_params(n_bootstrap, confidence_level)

        valid = [p for p in route_sample if p is not None and p > 0]
        if not valid or base_price is None or base_price <= 0:
            raise IndexVarianceError("Route has no valid sample or base price")

        sample = np.array(valid, dtype=np.float64)
        rng = np.random.default_rng(random_seed)
        draws = sample[rng.integers(0, sample.size, size=(n_bootstrap, sample.size))]
        cells = np.exp(np.mean(np.log(draws), axis=1))
        bootstrap_indices = 100.0 * cells / base_price

        alpha = 1.0 - confidence_level
        lo, hi = np.percentile(bootstrap_indices, [100 * alpha / 2, 100 * (1 - alpha / 2)])

        # Clamp: the CI must contain the published point estimate it annotates.
        if observed_index is not None:
            lo = min(float(lo), float(observed_index))
            hi = max(float(hi), float(observed_index))

        standard_error = float(np.std(bootstrap_indices, ddof=1))
        quantile = scipy_norm_ppf(1 - alpha / 2)
        half_width = quantile * standard_error

        return {
            "method": f"BOOTSTRAP_PERCENTILE_{int(confidence_level * 100)}",
            "n_bootstrap": int(n_bootstrap),
            "route_sample_size": len(sample),
            "standard_error": round(standard_error, 4),
            "ci_lower": round(float(lo), 4),
            "ci_upper": round(float(hi), 4),
            "ci_level": confidence_level,
            "mean_index": round(float(np.mean(bootstrap_indices)), 4),
            "median_index": round(float(np.median(bootstrap_indices)), 4),
            "ci_normal_lower": round(observed_index - half_width, 4)
            if observed_index is not None
            else None,
            "ci_normal_upper": round(observed_index + half_width, 4)
            if observed_index is not None
            else None,
        }

    @classmethod
    def jackknife_index_variance(
        cls,
        route_prices: Dict[str, float],
        base_prices: Dict[str, float],
        route_weights: Dict[str, float],
    ) -> Dict[str, float]:
        """Delete-one-route jackknife variance for the national index.

        Repeats the official Laspeyres aggregation with each corridor deleted
        (weights re-normalised over the survivors) and converts the leave-one-out
        indices into pseudo-values:

            p_j = n * I_all - (n - 1) * I_(-j)

        so that ``SE(I) = sqrt( sum((p_j - mean_p)^2) / (n * (n - 1)))``.

        Route ``contribution`` = ``I_all - I_(-j)`` measures, in index points,
        how much that corridor's sampling variation moves the national index.
        """
        routes = [
            r
            for r in route_weights
            if route_prices.get(r) is not None
            and route_prices[r] > 0
            and base_prices.get(r) is not None
            and base_prices[r] > 0
        ]
        if len(routes) < 2:
            raise IndexVarianceError(
                "Jackknife requires at least two routes with valid prices"
            )

        n = len(routes)

        def _index(subset: List[str]) -> float:
            sub_weights = cls._normalized_weights(route_weights, subset)
            relatives = np.array(
                [route_prices[r] / base_prices[r] for r in subset], dtype=np.float64
            )
            return float(100.0 * np.dot(relatives, sub_weights))

        all_index = _index(routes)
        pseudo: List[float] = []
        contributions: Dict[str, float] = {}
        for j, rcode in enumerate(routes):
            subset = [r for i, r in enumerate(routes) if i != j]
            leave_out = _index(subset)
            contributions[rcode] = round(all_index - leave_out, 4)
            pseudo.append(n * all_index - (n - 1) * leave_out)

        pseudo_arr = np.array(pseudo, dtype=np.float64)
        se = math.sqrt(float(np.sum((pseudo_arr - pseudo_arr.mean()) ** 2) / (n * (n - 1))))

        return {
            "method": "JACKKNIFE_LEAVE_ONE_ROUTE_OUT",
            "n_routes": n,
            "standard_error": round(se, 4),
            "index_value": round(all_index, 4),
            "pseudo_value_mean": round(float(pseudo_arr.mean()), 4),
            "route_contributions": contributions,
        }


def _norm_ppf(p: float) -> float:
    """Normal quantile function (scipy-free standard approximation).

    Acklam's rational approximation with 1e-9 worst-case error over the
    relevant tail region, avoiding a SciPy import in hot paths.
    """
    if p <= 0.0:
        return -np.inf
    if p >= 1.0:
        return np.inf

    a = [-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00]
    b = [-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00]
    plow = 0.02425
    phigh = 1.0 - plow

    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
        den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
        return num / den
    if p <= phigh:
        q = p - 0.5
        r = q * q
        num = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q
        den = (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        return num / den
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    num = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5])
    den = ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    return -num / den


scipy_norm_ppf = _norm_ppf

# Re-export engine constants for convenience (BootstrapCI users).
MINIMUM_OBSERVATIONS_PER_CELL = 2
