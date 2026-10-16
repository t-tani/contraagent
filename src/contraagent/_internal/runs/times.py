"""Times as run records write them: ISO 8601 in UTC (`2026-10-15T09:30:00+00:00`).

Every writer of a time takes it from `now_iso` (or `iso_of` for a timestamp it has), and
every reader parses one with `parse_iso`, so a record's times read the same everywhere.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

#: How much of a time is written: `seconds` in run records, `milliseconds` on a hub,
#: `microseconds` where order within a second matters.
Timespec = Literal["seconds", "milliseconds", "microseconds"]


def now() -> datetime:
    """The current time, timezone-aware, in UTC."""
    return datetime.now(UTC)


def now_iso(timespec: Timespec = "seconds") -> str:
    """The current time in UTC, ISO 8601, to `timespec`."""
    return now().isoformat(timespec=timespec)


def iso_of(ts: float, timespec: Timespec = "seconds") -> str:
    """A timestamp (seconds since the epoch) in UTC, ISO 8601, to `timespec`."""
    return datetime.fromtimestamp(ts, tz=UTC).isoformat(timespec=timespec)


def parse_iso(text: object) -> datetime | None:
    """An ISO 8601 time as a timezone-aware datetime: a trailing `Z` is UTC, and so is a
    time that names no zone. None for anything else: not a str, empty, or not a time."""
    if not isinstance(text, str) or not text:
        return None
    try:
        at = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return at if at.tzinfo is not None else at.replace(tzinfo=UTC)
