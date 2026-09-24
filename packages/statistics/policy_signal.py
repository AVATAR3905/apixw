"""Policy transmission classifier (APIX-2.2 Governance Intelligence).

For every index movement above a minimum elevation threshold, classifies the
current fare elevation as TRANSIENT or STRUCTURAL:

* **TRANSIENT** — spike reverses within 14 days, correlates with a calendar
  event (festival / peak-demand window), or is driven by a single carrier.
* **STRUCTURAL** — sustained above baseline for 21+ days, multi-carrier
  correlated, or correlated with an ATF price move.

Emits a single-line policy signal such as:

* ``TRANSIENT — Diwali demand surge, expected reversion by 2026-11-14``
* ``STRUCTURAL — ATF passthrough across 3 carriers, recommend CPI adjustment``

The framing targets RBI MPC-style readouts: distinguishing a festival blip from
structural fuel passthrough / oligopoly repricing is the monetary-policy use case
the coarse monthly CPI series cannot answer on time.
"""

import datetime
from typing import Any, Dict, List, Optional, Set

import numpy as np
from sqlalchemy.orm import Session

from packages.schemas.models import ATFPrice, FareObservation, IndexValue
from services.reference.festival_calendar import FestivalCalendarService

ELEVATION_THRESHOLD_PCT = 5.0
TRANSIENT_PERSISTENCE_DAYS = 14
STRUCTURAL_PERSISTENCE_DAYS = 21
ATF_ALIGNMENT_THRESHOLD_PCT = 1.0
SINGLE_CARRIER_SHARE_PCT = 60.0

_MONTH_FESTIVAL_LABELS = {
    1: "New Year travel window",
    8: "Independence Day long-weekend",
    10: "Dussehra travel cluster",
    11: "Diwali festive peak",
    12: "Christmas / New Year window",
}


def _festival_label(d: Optional[datetime.date]) -> str:
    if not d:
        return "peak-demand calendar event"
    return _MONTH_FESTIVAL_LABELS.get(d.month, f"{d.strftime('%B')} peak window")


def classify_elevation(
    values: List[float],
    dates: Optional[List[Optional[datetime.date]]] = None,
    calendar_dates: Optional[Set[datetime.date]] = None,
    carrier_breadth: int = 0,
    atf_move_pct: float = 0.0,
    elevation_threshold_pct: float = ELEVATION_THRESHOLD_PCT,
    transient_persistence_days: int = TRANSIENT_PERSISTENCE_DAYS,
    structural_persistence_days: int = STRUCTURAL_PERSISTENCE_DAYS,
    atf_alignment_threshold_pct: float = ATF_ALIGNMENT_THRESHOLD_PCT,
) -> Dict[str, Any]:
    """Classify an index series by the direction and persistence of its current elevation."""
    arr = np.array(values, dtype=np.float64)
    if len(arr) == 0:
        return {"mode": "NO_DATA", "reason": "insufficient index values"}

    # Baseline reference is the pre-spike level: median of the first half of the
    # window, so a long structural rise does not "pull up" its own reference.
    half = max(2, len(arr) // 2)
    baseline = float(np.median(arr[:half]))
    latest = float(arr[-1])
    if baseline <= 0:
        return {"mode": "NO_DATA", "reason": "invalid baseline"}

    elevation_pct = (latest - baseline) / baseline * 100.0
    elevated_now = elevation_pct >= elevation_threshold_pct

    tail = 0
    threshold_level = baseline * (1 + elevation_threshold_pct / 100.0)
    for v in arr[::-1]:
        if v >= threshold_level:
            tail += 1
        else:
            break
    persistence_days = tail

    ep_start = None
    if dates and len(dates) >= tail:
        ep_start = dates[-tail]
    episode_dates: Set[datetime.date] = set()
    if dates and tail:
        for d in dates[-tail:]:
            if d:
                episode_dates.add(d)
    calendar_dates = calendar_dates or set()
    calendar_aligned = bool(
        episode_dates & calendar_dates
    ) or (
        ep_start is not None
        and any(abs((cd - ep_start).days) <= 2 for cd in calendar_dates)
    )
    reversed_within_14 = persistence_days <= transient_persistence_days
    atf_aligned = atf_move_pct >= atf_alignment_threshold_pct
    multi_carrier = carrier_breadth >= 3
    single_carrier = 0 < carrier_breadth <= 1

    structural_score = (
        int(persistence_days >= structural_persistence_days)
        + int(multi_carrier)
        + int(atf_aligned)
    )
    transient_score = int(reversed_within_14) + int(calendar_aligned) + int(single_carrier)

    if not elevated_now:
        mode = "NO_ELEVATION"
        reason = f"latest index {latest:.2f} is within {elevation_threshold_pct:.1f}% of baseline median {baseline:.2f}"
    elif structural_score >= 2 and structural_score >= transient_score:
        mode = "STRUCTURAL"
        reason = "sustained + multi-carrier and/or ATF-aligned elevation"
    elif transient_score >= 2 and transient_score > structural_score:
        mode = "TRANSIENT"
        reason = "calendar-aligned and/or single-carrier-driven within transient window"
    elif structural_score == 1 and transient_score == 0:
        mode = "STRUCTURAL"
        reason = "single structural signal dominates"
    elif transient_score == 1 and structural_score == 0:
        mode = "TRANSIENT"
        reason = "single transient signal detected"
    else:
        mode = "MIXED"
        reason = "ambiguous structural and transient evidence"

    return {
        "mode": mode,
        "reason": reason,
        "baseline_median": round(baseline, 2),
        "latest_index": round(latest, 2),
        "elevation_pct": round(elevation_pct, 2),
        "persistence_days": persistence_days,
        "episode_start": ep_start.isoformat() if ep_start else None,
        "calendar_aligned": calendar_aligned,
        "atf_aligned": atf_aligned,
        "multi_carrier": multi_carrier,
        "single_carrier": single_carrier,
        "carrier_breadth": carrier_breadth,
        "atf_move_pct": round(atf_move_pct, 2),
        "structural_score": structural_score,
        "transient_score": transient_score,
    }


class PolicySignalClassifier:
    """Produces a monetary-policy-oriented signal from live index / ATF / availability data."""

    POLICY_DISCLOSURE = (
        "Policy classification is a rules-based decomposition of persistence, carrier breadth, "
        "calendar correlation, and ATF co-movement. It is an early-warning readout, not a "
        "forecast, and is intentionally conservative on structural claims."
    )

    @classmethod
    def evaluate(
        cls,
        db: Session,
        series: str = "BASE_FARE",
        series_type: str = "HEADLINE",
        index_type: str = "HEADLINE_T15",
        window_days: int = 60,
    ) -> Dict[str, Any]:
        """Evaluate the current national index elevation against calendar / ATF / carrier context."""
        rows = (
            db.query(IndexValue)
            .filter(
                IndexValue.index_series == series,
                IndexValue.series_type == series_type,
                IndexValue.index_type == index_type,
                IndexValue.route_id.is_(None),
            )
            .order_by(IndexValue.period_start.desc())
            .limit(window_days)
            .all()
        )
        rows = list(reversed(rows))
        if len(rows) < 5:
            return {
                "status": "INSUFFICIENT_DATA",
                "series": series,
                "series_type": series_type,
                "points_available": len(rows),
                "policy_line": None,
            }

        values = [r.index_value for r in rows]
        dates = [r.period_start for r in rows]
        calendar_dates = FestivalCalendarService.peak_date_set(db)

        latest_obs = rows[-1].period_start
        carrier_breadth = cls._carrier_breadth(db, latest_obs, lead_time=15)
        atf_move_pct = cls._atf_move_pct(db, window_days=window_days)

        result = classify_elevation(
            values=values,
            dates=dates,
            calendar_dates=calendar_dates,
            carrier_breadth=carrier_breadth,
            atf_move_pct=atf_move_pct,
        )

        policy_line = cls._one_line(
            db, result, episode_start=result.get("episode_start"),
            latest_obs=latest_obs, atf_move_pct=result.get("atf_move_pct"),
        )

        return {
            "status": "COMPLETED",
            "series": series,
            "series_type": series_type,
            "classification": result["mode"],
            "evidence": result,
            "policy_line": policy_line,
            "disclosure": cls.POLICY_DISCLOSURE,
        }

    @classmethod
    def _carrier_breadth(cls, db: Session, observation_date: datetime.date, lead_time: int = 15) -> int:
        """Distinct carriers contributing priceable inventory on the observation date."""
        count = (
            db.query(FareObservation.airline_id)
            .filter(
                FareObservation.search_timestamp
                >= datetime.datetime.combine(observation_date, datetime.time.min),
                FareObservation.search_timestamp
                <= datetime.datetime.combine(observation_date, datetime.time.max),
                FareObservation.advance_purchase_days == lead_time,
                FareObservation.availability_status == "AVAILABLE",
                FareObservation.base_fare > 0,
            )
            .distinct()
            .count()
        )
        return int(count or 0)

    @classmethod
    def _atf_move_pct(cls, db: Session, window_days: int = 60) -> float:
        """Latest vs window-open ATF price change for Delhi hub (0.0 when unavailable)."""
        records = (
            db.query(ATFPrice)
            .filter(ATFPrice.location == "Delhi")
            .order_by(ATFPrice.date.desc())
            .limit(max(window_days, 2))
            .all()
        )
        records = list(reversed(records))
        if len(records) < 2:
            return 0.0
        latest = records[-1].price_per_kl
        earliest = records[0].price_per_kl
        if not earliest:
            return 0.0
        return (latest - earliest) / earliest * 100.0

    @classmethod
    def _one_line(
        cls,
        db: Session,
        result: Dict[str, Any],
        episode_start: Optional[str],
        latest_obs: datetime.date,
        atf_move_pct: float,
    ) -> Optional[str]:
        mode = result.get("mode")
        if mode == "NO_DATA":
            return None
        if mode == "NO_ELEVATION":
            return (
                "Current fare elevation: NONE — index within normal band "
                f"({result.get('latest_index')} vs baseline {result.get('baseline_median')})."
            )
        if mode == "STRUCTURAL":
            carriers = "multi-carrier" if result.get("multi_carrier") else "carrier drift"
            fuel = (
                f" with ATF {atf_move_pct:+.1f}% co-movement"
                if result.get("atf_aligned")
                else ""
            )
            days = result.get("persistence_days", 0)
            day_txt = f"{days} day{'s' if days != 1 else ''}"
            return (
                f"Current fare elevation: STRUCTURAL — sustained {day_txt} "
                f"above baseline across {carriers}{fuel}; recommend CPI adjustment & passthrough review."
            )
        if mode == "TRANSIENT":
            calendar_txt = ""
            if result.get("calendar_aligned") and episode_start:
                start = datetime.date.fromisoformat(episode_start)
                calendar_txt = f" — {_festival_label(start)} demand surge"
            reversion = None
            if episode_start:
                start = datetime.date.fromisoformat(episode_start)
                reversion = start + datetime.timedelta(days=TRANSIENT_PERSISTENCE_DAYS)
            base = (
                f"Current fare elevation: TRANSIENT{calendar_txt}, "
                f"estimated +{result.get('elevation_pct')}% for "
                f"{result.get('persistence_days')} days"
            )
            if reversion:
                return f"{base}; expected reversion by {reversion.isoformat()}."
            return f"{base}."
        return (
            f"Current fare elevation: MIXED — sustained {result.get('persistence_days')} days "
            f"but no dominant structural or calendar narrative; monitor next 14 days."
        )
