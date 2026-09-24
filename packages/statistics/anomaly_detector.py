"""Standalone IQR/MAD anomaly detection and severity classification.

Produces per-point scores and an escalation classification that can be consumed
by a persistence service or directly in analytics endpoints.

Severity classification:
- NONE: within IQR inner fences and |z| < 2.5
- LOW: |z| in [2.5, 3.5) OR outside IQR inner fence but within outer fence
- MODERATE: |z| in [3.5, 5.0) OR outside IQR outer fence
- SEVERE: |z| >= 5.0
"""

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

import numpy as np

OUTLIER_MAD_THRESHOLD = 3.5
EXTREME_MAD_THRESHOLD = 5.0
IQR_INNER_MULTIPLIER = 1.5
IQR_OUTER_MULTIPLIER = 3.0
LOW_Z_THRESHOLD = 2.5
MODERATE_Z_THRESHOLD = 3.5
SEVERE_Z_THRESHOLD = 5.0
MIN_DEVIATION_PCT = 0.02  # practical-significance floor: |value-median|/median


@dataclass
class AnomalyHit:
    observation_date: Optional[date]
    value: float
    reference_median: float
    z_score: float
    iqr_inner_breach: bool
    iqr_outer_breach: bool
    severity: str  # NONE | LOW | MODERATE | SEVERE
    anomaly_type: str  # PRICE_OUTLIER | INDEX_SPIKE | FEED_DIVERGENCE


@dataclass
class AnomalyReport:
    series_name: str
    hits: List[AnomalyHit]
    total_points: int
    reference_median: float
    reference_mad: float
    iqr_inner_lower: float
    iqr_inner_upper: float
    iqr_outer_lower: float
    iqr_outer_upper: float
    summary_counts: dict = field(default_factory=dict)


@dataclass
class EscalationReport:
    anomaly_type: str
    date_range_start: Optional[date]
    date_range_end: Optional[date]
    total_hits: int
    max_severity: str
    consecutive_count: int
    is_escalated: bool
    escalation_reason: str


SEVERITY_ORDER = {"NONE": 0, "LOW": 1, "MODERATE": 2, "SEVERE": 3}


def _mad_z_scores(values: np.ndarray) -> np.ndarray:
    """Return MAD-based robust z-scores for each element in values."""
    if len(values) < 3:
        return np.zeros(len(values))
    median = np.median(values)
    mad = np.median(np.abs(values - median))
    if mad == 0:
        return np.zeros(len(values))
    return 0.6745 * (values - median) / mad


def _classify_severity(z: float, iqr_inner: bool, iqr_outer: bool) -> str:
    """Map |z| and IQR fence breach to a severity label."""
    abs_z = abs(z)
    if abs_z >= SEVERE_Z_THRESHOLD or iqr_outer:
        return "SEVERE"
    if abs_z >= MODERATE_Z_THRESHOLD:
        return "MODERATE"
    if abs_z >= LOW_Z_THRESHOLD or iqr_inner:
        return "LOW"
    return "NONE"


def detect_on_values(
    values: List[float],
    dates: Optional[List[Optional[date]]] = None,
    series_name: str = "",
    anomaly_type: str = "PRICE_OUTLIER",
    min_deviation_pct: float = MIN_DEVIATION_PCT,
) -> AnomalyReport:
    """Run IQR + MAD detection on a list of values and return AnomalyReport."""
    arr = np.array(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    n = len(arr)
    if n == 0:
        return AnomalyReport(
            series_name=series_name,
            hits=[],
            total_points=0,
            reference_median=0.0,
            reference_mad=0.0,
            iqr_inner_lower=0.0,
            iqr_inner_upper=0.0,
            iqr_outer_lower=0.0,
            iqr_outer_upper=0.0,
            summary_counts={"NONE": 0, "LOW": 0, "MODERATE": 0, "SEVERE": 0},
        )

    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    q1 = float(np.percentile(arr, 25))
    q3 = float(np.percentile(arr, 75))
    iqr = q3 - q1
    inner_lo = q1 - IQR_INNER_MULTIPLIER * iqr
    inner_hi = q3 + IQR_INNER_MULTIPLIER * iqr
    outer_lo = q1 - IQR_OUTER_MULTIPLIER * iqr
    outer_hi = q3 + IQR_OUTER_MULTIPLIER * iqr

    z_all = _mad_z_scores(arr)
    counts = {"NONE": 0, "LOW": 0, "MODERATE": 0, "SEVERE": 0}
    hits: List[AnomalyHit] = []

    for i in range(n):
        z = float(z_all[i])
        v = float(arr[i])
        inner_breach = v < inner_lo or v > inner_hi
        outer_breach = v < outer_lo or v > outer_hi
        sev = _classify_severity(z, inner_breach, outer_breach)
        # Practical-significance floor: statistical outlier is not operationally
        # relevant unless it represents a material move off the reference median.
        pct_dev = abs(v - median) / median if median else 0.0
        if pct_dev < min_deviation_pct:
            sev = "NONE"
        counts[sev] += 1
        if sev != "NONE":
            dt = dates[i] if dates and i < len(dates) else None
            hits.append(
                AnomalyHit(
                    observation_date=dt,
                    value=v,
                    reference_median=round(median, 2),
                    z_score=round(z, 4),
                    iqr_inner_breach=inner_breach,
                    iqr_outer_breach=outer_breach,
                    severity=sev,
                    anomaly_type=anomaly_type,
                )
            )

    return AnomalyReport(
        series_name=series_name,
        hits=hits,
        total_points=n,
        reference_median=round(median, 2),
        reference_mad=round(mad, 2),
        iqr_inner_lower=round(inner_lo, 2),
        iqr_inner_upper=round(inner_hi, 2),
        iqr_outer_lower=round(outer_lo, 2),
        iqr_outer_upper=round(outer_hi, 2),
        summary_counts=counts,
    )


def escalate_hits(
    hits: List[AnomalyHit],
    anomaly_type: str = "",
    consecutive_threshold: int = 2,
) -> EscalationReport:
    """Determine whether a sequence of hits constitutes an escalation event.

    A hit is escalated when:
      - severity is SEVERE, OR
      - severity >= MODERATE and the same type has fired on consecutive days.
    """
    if not hits:
        return EscalationReport(
            anomaly_type=anomaly_type,
            date_range_start=None,
            date_range_end=None,
            total_hits=0,
            max_severity="NONE",
            consecutive_count=0,
            is_escalated=False,
            escalation_reason="no anomalies detected",
        )

    max_sev = max(SEVERITY_ORDER[h.severity] for h in hits)
    max_sev_label = [k for k, v in SEVERITY_ORDER.items() if v == max_sev][0]
    sorted_hits = sorted(hits, key=lambda h: h.observation_date or date.min)
    dates_sorted = [h.observation_date for h in sorted_hits]

    consecutive = 1
    for i in range(1, len(dates_sorted)):
        if dates_sorted[i] and dates_sorted[i - 1] and (dates_sorted[i] - dates_sorted[i - 1]).days <= 1:
            consecutive += 1
        else:
            consecutive = 1

    is_escalated = max_sev_label == "SEVERE" or (
        max_sev >= SEVERITY_ORDER["MODERATE"] and consecutive >= consecutive_threshold
    )
    reason = ""
    if is_escalated:
        if max_sev_label == "SEVERE":
            reason = f"severe anomaly detected (consecutive_run={consecutive})"
        else:
            reason = f"consecutive anomaly across {consecutive} observations above moderate threshold"

    return EscalationReport(
        anomaly_type=anomaly_type,
        date_range_start=dates_sorted[0],
        date_range_end=dates_sorted[-1],
        total_hits=len(hits),
        max_severity=max_sev_label,
        consecutive_count=consecutive,
        is_escalated=is_escalated,
        escalation_reason=reason,
    )
