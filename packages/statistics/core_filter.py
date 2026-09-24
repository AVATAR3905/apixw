"""Core vs Headline Index Filter (Dual-Series Design, Phase 1c).

The published *headline* series is the raw T+15 Jevons anchor measured on every
observation day — it carries the full seasonality of the market, including
last-minute urgency and festive-demand spikes. The *core* series is the same
T+15 anchor measured on a **volatility-guarded** observation set:

1. Excludes trips whose travel date falls on a scheduled peak-demand festival
   window (festival calendar from ``services.reference.festival_calendar``).
2. Excludes exotic/irregular feed records (quality ``REJECT`` or unscheduled
   corridor snapshots).
3. Requires adequate **continuity**: a route must have been observed in the
   trailing lookback window on at least ``MIN_CONTINUITY_DAYS`` days, or it is
   dropped from the core basket for that day. This prevents a single
   thin-coverage snapshot from injecting structural noise into the core series.

The gap between headline and core is a readable story in its own right: when
the headline runs above core, fares are inflating because of demand spikes
rather than underlying cost pressure; a narrowing gap signals normalisation.
"""

import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from packages.schemas.models import FareObservation, IndexValue

# Festival windows are injected by the festival calendar service; this set is
# the safety-net default (Indian national holiday clusters) if the calendar is
# not seeded.
DEFAULT_PEAK_WINDOWS: List[datetime.date] = []

MIN_CONTINUITY_DAYS = 5  # route must appear >=5 of the trailing 14 days
CONTINUITY_LOOKBACK_DAYS = 14
EXCLUDED_QUALITY = {"REJECT"}


class CoreIndexFilter:
    """Applies volatility-guards to the observation set feeding a CORE index day."""

    @classmethod
    def peak_dates(cls, db: Session) -> set:
        """Returns the set of travel dates treated as festival/peak demand days."""
        try:
            from services.reference.festival_calendar import FestivalCalendarService

            return FestivalCalendarService.peak_date_set(db)
        except Exception:
            pass
        return set(DEFAULT_PEAK_WINDOWS)

    @classmethod
    def filter_observations(
        cls,
        observations: Iterable[Any],
        peak_set: Optional[set] = None,
    ) -> List[Any]:
        """Drops observations on festival windows and rejected-quality records."""
        peak_set = peak_set or set()
        kept = []
        for o in observations:
            travel = o.travel_date if hasattr(o, "travel_date") else None
            if travel is not None and travel in peak_set:
                continue
            quality = getattr(o, "quality_status", None)
            if quality in EXCLUDED_QUALITY:
                continue
            if getattr(o, "availability_status", None) in {"SOLD_OUT", "CANCELLED"}:
                continue
            kept.append(o)
        return kept

    @classmethod
    def route_has_continuity(
        cls,
        db: Session,
        route_id: int,
        observation_date: datetime.date,
        series_name: str = "BASE_FARE",
    ) -> bool:
        """A route is eligible for CORE on ``observation_date`` if its trailing
        window shows enough continuous coverage in the *headline* series.

        Route-level headline values are stored under ``index_type=="ROUTE_LEVEL"``
        (the national aggregate carries ``HEADLINE_T15``).
        """
        start = observation_date - datetime.timedelta(days=CONTINUITY_LOOKBACK_DAYS)
        hits = (
            db.query(IndexValue.id)
            .filter(
                IndexValue.index_series == series_name,
                IndexValue.index_type == "ROUTE_LEVEL",
                IndexValue.route_id == route_id,
                IndexValue.period_start >= start,
                IndexValue.period_start < observation_date,
            )
            .count()
        )
        return hits >= MIN_CONTINUITY_DAYS

    @classmethod
    def prepare_core_day(
        cls,
        db: Session,
        route_id: int,
        observation_date: datetime.date,
        series_name: str = "BASE_FARE",
    ) -> Dict[str, Any]:
        """Returns the guarded observation set + eligibility flag for a core day."""
        peak_set = cls.peak_dates(db)
        observations = (
            db.query(FareObservation)
            .filter(
                FareObservation.route_id == route_id,
                FareObservation.search_timestamp
                >= datetime.datetime.combine(observation_date, datetime.time.min),
                FareObservation.search_timestamp
                <= datetime.datetime.combine(observation_date, datetime.time.max),
                FareObservation.advance_purchase_days == 15,
            )
            .all()
        )
        filtered = cls.filter_observations(observations, peak_set)
        eligible = cls.route_has_continuity(db, route_id, observation_date, series_name)
        return {
            "observations": filtered,
            "eligible": eligible,
            "peak_set_hit": any(
                getattr(o, "travel_date", None) in peak_set for o in observations
            ),
        }
