"""The time stamps of Euro-Q-Exa, read as Central European time.

The stamps carry no zone (they matched German time); the EU rule is written out, so no zone database is needed.
"""

from datetime import UTC, datetime, timedelta
from typing import Final

from ..clock import seconds_between

_AGREE: Final = timedelta(minutes=5)   # the most timestamp_submitted may differ from submitted_utc
STAMPS: Final = ("timestamp_submitted", "timestamp_scheduled", "timestamp_completed")    # in a result answer


def _change(year: int, month: int) -> datetime:
    """01:00 UTC on the last Sunday of a month (March or October): the moment the clocks change."""
    last = datetime(year, month + 1, 1, 1, tzinfo=UTC) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() + 1) % 7)


def offset(moment: datetime) -> timedelta:
    """The offset of Central European time from UTC at a moment in UTC."""
    summer = _change(moment.year, 3) <= moment < _change(moment.year, 10)
    return timedelta(hours=2 if summer else 1)


def readings(stamp: object) -> list[datetime]:
    """The moments in UTC that a stamp of the site can be, earliest first; none for a stamp that cannot be read."""
    try:
        wall = datetime.fromisoformat(str(stamp))
        if wall.tzinfo is not None:
            return [wall.astimezone(UTC)]
        wall = wall.replace(tzinfo=UTC)
        # Two in the hour the October change repeats, none in the hour the March change skips.
        return [wall - hours for hours in (timedelta(hours=2), timedelta(hours=1)) if offset(wall - hours) == hours]
    except (ValueError, OverflowError):
        return []


def _moment(value: object) -> datetime | None:
    """A time of the app (ISO, with its zone) as a moment in UTC, or None."""
    try:
        moment = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return moment.astimezone(UTC) if moment.tzinfo is not None else None


def _ways(first: datetime, stamps: list[object]) -> list[tuple[datetime, ...]]:
    """Each way to read the later stamps in turn, every reading not before the one before it."""
    ways = [(first,)]
    for stamp in stamps:
        ways = [(*way, moment) for way in ways for moment in readings(stamp) if moment >= way[-1]]
    return ways


def site_times(reply: dict, submitted_utc: str | None) -> dict:
    """seconds, scheduled_utc, completed_utc and zone_check of a result, against the app's own submitted_utc."""
    submitted, scheduled, completed = (reply.get(key) for key in STAMPS)
    app = _moment(submitted_utc)
    first = None if app is None else min(readings(submitted), key=lambda t: abs(t - app), default=None)
    ways = _ways(first, [scheduled, completed]) if first is not None and abs(first - app) <= _AGREE else []
    if len(ways) != 1:        # none fits within _AGREE, or two fit an hour apart: the stamps as written
        return {"seconds": seconds_between(scheduled, completed, 6), "scheduled_utc": None, "completed_utc": None,
                "zone_check": False}
    _, start, end = ways[0]
    return {"seconds": round((end - start).total_seconds(), 6), "scheduled_utc": start.isoformat(),
            "completed_utc": end.isoformat(), "zone_check": True}
