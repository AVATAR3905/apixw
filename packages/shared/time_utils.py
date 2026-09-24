"""Timezone helpers shared across the Observatory.

The schema uses naive ``DateTime`` columns storing UTC wall-clock times, so a
single naive-UTC producer keeps every write consistent regardless of the
process timezone and avoids both the deprecated ``datetime.utcnow()`` and the
offset-aware/naive mismatch that would arise if some write paths used
``datetime.now(UTC)`` directly.
"""

import datetime


def utcnow() -> datetime.datetime:
    """Return the current UTC wall-clock time as a naive ``datetime``.

    Equivalent to the old ``datetime.datetime.utcnow()`` but written without the
    deprecated API. Naive on purpose: the SQLAlchemy ``DateTime`` columns are
    naive, and PostgreSQL rejects offset-aware values for them.
    """
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
