"""Speed + stability surface over the *real* statistical rungs on disk.

Measured rungs (imported by path -- the actual interpreter surfaces them, so
nothing here is recalled or guessed):

    packages/statistics/variance.py
        IndexVarianceEstimator.bootstrap_index_variance  (bootstrap CI rung)
        IndexVarianceEstimator.jackknife_index_variance  (deterministic rung)

The OCR/VLM rungs of the extraction ladder are deliberately NOT benchmarked
here: no paddleocr / tesseract / VLM runtime is installed on this machine, so
any number for them would be fabricated.  They are documented (not measured)
in PIPELINE_BENCHMARK.md, and the config switch ``EXTRACTION_OCR_BACKEND``
degrades through ExtractionNotAvailable when an engine is absent.

Output is informational only; it asserts nothing and fails loudly only when a
rung genuinely cannot run (honesty contract: no fabricated numbers).
"""

from __future__ import annotations

import os
import sys
import time
from typing import Dict, List

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.statistics.variance import IndexVarianceEstimator  # noqa: E402

N_ROUTES = 40
N_CARRIERS = 6
BOOTSTRAP_SURFACE = [500, 2000, 10000]


def _synthetic_corpus(seed: int = 7) -> Dict[str, object]:
    rng = np.random.default_rng(seed)
    routes = [f"DEL-BOM-{i:02d}" for i in range(N_ROUTES)]
    route_samples: Dict[str, List[float]] = {}
    base_prices: Dict[str, float] = {}
    for r in routes:
        base = float(rng.uniform(2500.0, 8500.0))
        base_prices[r] = base
        route_samples[r] = [float(base * v) for v in rng.lognormal(0.0, 0.10, N_CARRIERS)]
    raw = rng.random(N_ROUTES)
    route_weights = {r: float(w) for r, w in zip(routes, raw / raw.sum())}
    return {
        "route_samples": route_samples,
        "base_prices": base_prices,
        "route_weights": route_weights,
        "routes": routes,
    }


def _observe_index(
    route_samples: Dict[str, List[float]],
    base_prices: Dict[str, float],
    route_weights: Dict[str, float],
    routes: List[str],
) -> float:
    """Deterministic point estimate mirroring a single published cell."""
    total = 0.0
    wsum = 0.0
    for r in routes:
        s = [p for p in route_samples[r] if p > 0]
        if not s or base_prices[r] <= 0:
            continue
        geom = float(np.exp(np.mean(np.log(s))))
        w = route_weights[r]
        total += w * (100.0 * geom / base_prices[r])
        wsum += w
    return total / wsum


def _bootstrap_row(
    est: IndexVarianceEstimator,
    n_bootstrap: int,
    corpus: Dict[str, object],
    observed: float,
) -> Dict[str, float]:
    t0 = time.perf_counter()
    out = est.bootstrap_index_variance(
        route_samples=corpus["route_samples"],
        base_prices=corpus["base_prices"],
        route_weights=corpus["route_weights"],
        observed_index=observed,
        n_bootstrap=n_bootstrap,
        confidence_level=0.95,
        random_seed=11,
    )
    dt = (time.perf_counter() - t0) * 1e3
    return {
        "n_bootstrap": n_bootstrap,
        "ms": dt,
        "se": out["standard_error"],
        "ci_lower": out["ci_lower"],
        "ci_upper": out["ci_upper"],
        "mean_index": out["mean_index"],
        "median_index": out["median_index"],
        "bias": out["bias"],
    }


def _jackknife_result(
    est: IndexVarianceEstimator,
    corpus: Dict[str, object],
) -> Dict[str, float]:
    route_prices: Dict[str, float] = {}
    for r, v in corpus["route_samples"].items():
        s = [p for p in v if p > 0]
        route_prices[r] = float(np.exp(np.mean(np.log(s))))
    t0 = time.perf_counter()
    out = est.jackknife_index_variance(
        route_prices=route_prices,
        base_prices=corpus["base_prices"],
        route_weights=corpus["route_weights"],
    )
    dt = (time.perf_counter() - t0) * 1e3
    return {
        "n_routes": int(out["n_routes"]),
        "ms": dt,
        "se": out["standard_error"],
        "index_value": out["index_value"],
    }


def main() -> None:
    est = IndexVarianceEstimator
    corpus = _synthetic_corpus()
    observed = _observe_index(
        corpus["route_samples"], corpus["base_prices"], corpus["route_weights"], corpus["routes"]
    )
    print(f"point index (observed)      = {observed:.4f}")
    print("n_bootstrap |    ms   |   se    | ci 95%            | mean   | median | bias")
    for n in BOOTSTRAP_SURFACE:
        r = _bootstrap_row(est, n, corpus, observed)
        print(
            f"{r['n_bootstrap']:>11} | {r['ms']:6.2f} | {r['se']:6.4f} | "
            f"{r['ci_lower']:7.3f}-{r['ci_upper']:7.3f} | {r['mean_index']:6.3f} | "
            f"{r['median_index']:7.3f} | {r['bias']:+.4f}"
        )
    jr = _jackknife_result(est, corpus)
    print(
        f"jackknife       | {jr['ms']:6.2f} | {jr['se']:6.4f} | (deterministic)      | "
        f"{jr['index_value']:6.3f} | n_routes={jr['n_routes']}"
    )
    # Stability of the bootstrap rung across independent seeds at the largest
    # surface point: SE must not move materially when the seed changes.
    ses = []
    for seed in range(6):
        out = est.bootstrap_index_variance(
            route_samples=corpus["route_samples"],
            base_prices=corpus["base_prices"],
            route_weights=corpus["route_weights"],
            observed_index=observed,
            n_bootstrap=10000,
            confidence_level=0.95,
            random_seed=seed,
        )
        ses.append(out["standard_error"])
    print(
        f"SE across 6 seeds (B=10000): mean={np.mean(ses):.6f} sd={np.std(ses):.6f} "
        f"rel_sd={np.std(ses) / np.mean(ses) * 100:.4f}%"
    )


if __name__ == "__main__":
    main()
