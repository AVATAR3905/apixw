"""Festival / peak-demand calendar service (Dual-Series CORE guard, Phase 1c).

Provides the observatory's notion of *peak-demand travel windows* used to strip
festive spikes out of the CORE index series.  In the current build the calendar
is a curated static table (national holiday clusters); Phase 6 replaces it with
a seeded ``festival_events`` table plus a dashboard overlay.
"""

import datetime
from typing import List, Set

from sqlalchemy.orm import Session

# Curated Indian national holiday / festive travel clusters (YYYY-MM-DD).
# These are the windows where domestic air demand (and fares) structureally
# spikes, and which the CORE series deliberately excludes:
#   - Independence Day long weekend
#   - Festival travel season (Dussehra / Diwali window)
_PEAK_WINDOWS: List[datetime.date] = [
    datetime.date(2026, 8, 14),  # Independence Day eve
    datetime.date(2026, 8, 15),
    datetime.date(2026, 8, 16),  # long-weekend return spike
    datetime.date(2026, 10, 17),  # Dussehra cluster
    datetime.date(2026, 10, 18),
    datetime.date(2026, 10, 19),
    datetime.date(2026, 11, 6),  # Diwali / festive peak
    datetime.date(2026, 11, 7),
    datetime.date(2026, 11, 8),
    datetime.date(2026, 11, 13),  # Bhai Dooj
    datetime.date(2026, 11, 14),
    datetime.date(2026, 12, 24),  # Christmas / New Year window
    datetime.date(2026, 12, 25),
    datetime.date(2026, 12, 26),
    datetime.date(2026, 12, 31),
    datetime.date(2027, 1, 1),
]


class FestivalCalendarService:
    """Curated peak-demand calendar + CORE-series helpers."""

    @classmethod
    def peak_date_set(cls, db: Session) -> Set[datetime.date]:
        """Returns the travel dates treated as peak-demand windows for CORE guards."""
        return set(_PEAK_WINDOWS)

    @classmethod
    def all_events(cls, db: Session) -> List[dict]:
        """Returns the full festival calendar as JSON-serializable dicts."""
        return [
            {"date": d.isoformat(), "event": "PEAK_DEMAND_WINDOW", "labelled": True}
            for d in _PEAK_WINDOWS
        ]
