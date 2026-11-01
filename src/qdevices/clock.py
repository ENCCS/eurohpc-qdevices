"""The clock of the app: the time in UTC, the seconds of the waits, and the sleep between two polls."""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Final, Protocol, TypeAlias

Sleep: TypeAlias = Callable[[float], None]


class Clock(Protocol):
    """What the app asks of a clock: the time in UTC, and seconds that never go back."""

    def utc(self) -> datetime:
        """The time now, in UTC."""

    def monotonic(self) -> float:
        """Seconds from a fixed moment that never go back: the deadlines of the waits."""


class _SystemClock:
    """The clock of the system."""

    def utc(self) -> datetime:
        """The time now, in UTC."""
        return datetime.now(UTC)

    def monotonic(self) -> float:
        """The seconds of the monotonic clock of the system."""
        return time.monotonic()


CLOCK: Final[Clock] = _SystemClock()   # no slots: a test sets its utc
SLEEP: Final[Sleep] = time.sleep


def stamp(when: datetime) -> str:
    """The UTC stamp of a file name, in the form YYYYMMDDTHHMMSSZ."""
    return when.strftime("%Y%m%dT%H%M%SZ")


def seconds_between(start: object, end: object, digits: int) -> float | None:
    """The seconds from one ISO time to another, or None if either cannot be read."""
    try:
        return round((datetime.fromisoformat(str(end)) - datetime.fromisoformat(str(start))).total_seconds(),
                     digits)
    except (TypeError, ValueError):
        return None
