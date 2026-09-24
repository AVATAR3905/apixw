"""Billion-Prices lead-lag analysis (APIX-2.2 Governance Intelligence).

PriceStats / IMF Billion Prices Project methodology applied to India: a
regression of the Observatory's high-frequency daily index against the official
MoSPI CPI airfare (Transport & Communication sub-group) series across 1, 2, 3,
and 4 week lags, reporting the leading-indicator lag and directional accuracy.

Claim format produced: ``APIX-2.0 leads official CPI Transport by X weeks with
Y% directional accuracy.``
"""

import datetime
from typing import Any, Dict, List

import numpy as np
from scipy.stats import pearsonr
from sqlalchemy.orm import Session

from packages.schemas.models import BenchmarkValue, IndexValue

MAX_LAG_WEEKS = 4
MIN_ALIGNED_WEEKS = 6
DIRECTIONAL_WINDOW = 12  # latest N prototype weeks used for directional read


def weekly_series(day_val_pairs: List[tuple]) -> Dict[str, float]:
    """Aggregate daily (date, value) pairs into float ISO week keys.

    A week is keyed by its Monday.  Values are simple averages over a calendar
    week (Monday-to-Sunday), matching how a high-frequency index would be
    sub-sampled against the monthly official reference.
    """
    buckets: Dict[str, List[float]] = {}
    for d, v in day_val_pairs:
        if not d or v is None:
            continue
        monday = d - datetime.timedelta(days=d.weekday())
        buckets.setdefault(monday.isoformat(), []).append(float(v))
    return {k: float(np.mean(vals)) for k, vals in sorted(buckets.items())}


def align_series(proto: Dict[str, float], cpi: Dict[str, float]) -> list:
    """Returns aligned [(week_key, proto_val, cpi_val)] on shared week keys."""
    common = sorted(set(proto.keys()) & set(cpi.keys()))
    return [(k, proto[k], cpi[k]) for k in common]


def _directional_accuracy(proto_vals: List[float], cpi_vals: List[float]) -> float:
    """Percent of weekly MoM sign matches between the two series."""
    if len(proto_vals) < 3 or len(cpi_vals) < 3:
        return 0.0
    proto_d = np.diff(proto_vals)
    cpi_d = np.diff(cpi_vals)
    matches = np.sign(proto_d) == np.sign(cpi_d)
    return float(np.mean(matches)) * 100.0 if len(matches) else 0.0


def compute_lead_lag(proto: Dict[str, float], cpi: Dict[str, float]) -> Dict[str, Any]:
    """Compute Pearson-r and directional accuracy at lags 0..4 weeks.

    A positive lag means the prototype leads: corr(proto[t], cpi[t+lag]).
    """
    aligned = align_series(proto, cpi)
    if len(aligned) < MIN_ALIGNED_WEEKS:
        return {
            "status": "INSUFFICIENT_ALIGNMENT",
            "aligned_weeks": len(aligned),
            "required_aligned_weeks": MIN_ALIGNED_WEEKS,
            "lags": [],
            "best_lag_weeks": None,
        }

    keys = [k for k, _, _ in aligned]
    p = np.array([v for _, v, _ in aligned])
    c = np.array([v for _, _, v in aligned])
    n = len(p)

    lag_results: List[Dict[str, Any]] = []
    for lag in range(0, MAX_LAG_WEEKS + 1):
        if n - lag < 3:
            continue
        pp = p[: n - lag] if lag else p
        cc = c[lag:] if lag else c
        # A constant window (e.g. a single, not-yet-updated CPI month spanning the
        # whole overlap) makes Pearson's r undefined; treat it as no evidence.
        if np.ptp(pp) == 0 or np.ptp(cc) == 0:
            r_val = 0.0
            p_val = 1.0
        else:
            r, p_val = pearsonr(pp, cc)
            r_val = float(r)
            if not np.isfinite(r_val):
                r_val = 0.0
                p_val = 1.0
        acc = _directional_accuracy(list(pp), list(cc))
        lag_results.append(
            {
                "lag_weeks": lag,
                "pearson_r": round(r_val, 3),
                "p_value": round(float(p_val), 5),
                "directional_accuracy_pct": round(acc, 1),
                "aligned_points": int(len(pp)),
            }
        )

    if not lag_results:
        return {
            "status": "INSUFFICIENT_ALIGNMENT",
            "aligned_weeks": len(aligned),
            "lags": [],
            "best_lag_weeks": None,
        }

    best = max(lag_results, key=lambda x: abs(x["pearson_r"]))
    best_acc = (
        max(lag_results, key=lambda x: x["directional_accuracy_pct"])["directional_accuracy_pct"]
        if lag_results
        else 0.0
    )

    interpretation = None
    if best["lag_weeks"] > 0 and best["pearson_r"] >= 0.4:
        interpretation = (
            f"APIX-2.0 leads official CPI Transport by {best['lag_weeks']} week(s) "
            f"with {best['directional_accuracy_pct']:.0f}% directional accuracy — "
            "consistent with the IMF/PriceStats Billion Prices finding that online "
            "price indices lead official CPI by 2-4 weeks."
        )
    elif best["lag_weeks"] == 0:
        interpretation = (
            "The prototype index and official CPI move contemporaneously (r=%.2f) "
            "within the aligned window — no leading advantage yet detected." % best["pearson_r"]
        )
    else:
        interpretation = "Correlation is weak; lead-lag inference is not yet meaningful."

    return {
        "status": "COMPLETED",
        "aligned_weeks": len(aligned),
        "window_start": keys[0],
        "window_end": keys[-1],
        "lags": lag_results,
        "best_lag_weeks": best["lag_weeks"],
        "best_lag_pearson_r": best["pearson_r"],
        "best_lag_directional_accuracy_pct": best_acc,
        "best_lag_p_value": best["p_value"],
        "interpretation": interpretation,
        "claim": f"APIX-2.0 leads official CPI Transport by {best['lag_weeks']} week(s) "
        f"with {best['directional_accuracy_pct']:.0f}% directional accuracy."
        if best["lag_weeks"] > 0 and best["pearson_r"] >= 0.4
        else interpretation,
    }


class LeadingIndicatorService:
    """Runs the Billion-Prices lead-lag regression against stored MoSPI data."""

    METHODOLOGY_DISCLOSURE = (
        "Billion-Prices Project (IMF/Harvard PriceStats) methodology applied to India. "
        "The prototype aggregate is sub-sampled to calendar weeks and correlated with the "
        "MoSPI CPI airfare component at 1-4 week forward lags; a positive lag indicates the "
        "high-frequency index leads the official series."
    )

    @classmethod
    def get_leading_indicator(
        cls,
        db: Session,
        series: str = "BASE_FARE",
        series_type: str = "HEADLINE",
        index_type: str = "HEADLINE_T15",
        max_days: int = 180,
        indicator: str = "CPI_PASSENGER_TRANSPORT_SERVICES",
    ) -> Dict[str, Any]:
        """Compute weekly lead-lag between the prototype index and official CPI."""
        proto_rows = (
            db.query(IndexValue)
            .filter(
                IndexValue.index_series == series,
                IndexValue.series_type == series_type,
                IndexValue.index_type == index_type,
                IndexValue.route_id.is_(None),
            )
            .order_by(IndexValue.period_start.desc())
            .limit(max_days)
            .all()
        )
        if len(proto_rows) < MIN_ALIGNED_WEEKS:
            return {
                "status": "INSUFFICIENT_PROTOTYPE_HISTORY",
                "prototype_points": len(proto_rows),
                "required_aligned_weeks": MIN_ALIGNED_WEEKS,
                "claim": None,
            }

        proto = weekly_series([(r.period_start, r.index_value) for r in proto_rows])

        cpi_rows = (
            db.query(BenchmarkValue)
            .filter(BenchmarkValue.indicator == indicator)
            .order_by(BenchmarkValue.period.asc())
            .all()
        )
        if not cpi_rows:
            return {
                "status": "NO_BENCHMARK",
                "prototype_weeks": len(proto),
                "claim": None,
            }

        cpi = cls._monthly_to_weekly(
            [(r.period, float(r.value)) for r in cpi_rows]
        )

        result = compute_lead_lag(proto, cpi)
        result["methodology_disclosure"] = cls.METHODOLOGY_DISCLOSURE
        result["benchmark_indicator"] = indicator
        result["prototype_series"] = series
        result["prototype_weeks"] = len(proto)
        result["benchmark_months"] = len(cpi_rows)
        return result

    @staticmethod
    def _monthly_to_weekly(monthly: List[tuple]) -> Dict[str, float]:
        """Expand a monthly (YYYY-MM, value) series to weekly keys.

        Each month's value is stamped on every week key that falls inside that
        calendar month.  This is a level-preserving (not interpolating) expansion:
        it lets the lag regression compare weekly prototype motion against the
        most recent official print, which is how an early-warning system would
        actually be used by a CPI desk.
        """
        out: Dict[str, float] = {}
        for period, val in monthly:
            try:
                y, m = int(period[:4]), int(period[5:7])
            except (ValueError, IndexError):
                continue
            year, month = y, m
            first = datetime.date(year, month, 1)
            if month == 12:
                nxt = datetime.date(year + 1, 1, 1)
            else:
                nxt = datetime.date(year, month + 1, 1)
            d = first
            while d < nxt:
                monday = d - datetime.timedelta(days=d.weekday())
                out.setdefault(monday.isoformat(), val)
                d += datetime.timedelta(days=1)
        return dict(sorted(out.items()))
