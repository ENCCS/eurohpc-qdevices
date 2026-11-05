"""The stops of one order at the calls of a record: when `resolve --expired` and `--unreadable` take it.

A result_error stop got an answer that could not be used, or no usable answer: missed polls up to wait_seconds, a
redirect or an HTTP error of 400 or more, or a stop line written before 0.2.0, which has no key missed.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final, Self

EXPIRED_MINUTES: Final = 10     # two calls this far apart: --expired; --unreadable on answers that could not be used
UNANSWERED_HOURS: Final = 24    # two calls this far apart: --unreadable on any result_error stops


def answered(stop: dict) -> bool:
    """True for a result_error stop on an answer that could not be used: missed null, no HTTP status of 300 or more."""
    status = stop.get("http_status")
    return "missed" in stop and stop["missed"] is None and not (isinstance(status, int) and status >= 300)


def _result_error(stop: dict) -> bool:
    return stop.get("kind") == "result_error"


@dataclass(frozen=True, slots=True)
class Stops:
    """The stop lines of one order, each with the number of its call, in the order of the record."""

    found: tuple[tuple[dict, int], ...]

    @classmethod
    def of(cls, events: list[dict], order: int) -> Self:
        """The stops of an order in the lines of a record; each start or resume line begins a call."""
        calls, found = 0, []
        for e in events:
            if e.get("event") in ("start", "resume"):
                calls += 1
            elif e.get("event") == "stop" and e.get("order") == order:
                found.append((e, calls))
        return cls(tuple(found))

    def expired(self) -> str | None:
        """Why --expired does not take the order, or None when it does."""
        if not self._last("result_expired"):
            return "its last stop is not result_expired"
        span = self._span(lambda stop: stop.get("kind") == "result_expired")
        if span is None:
            return f"one call only got that answer: resume once more, {EXPIRED_MINUTES} minutes or more later"
        if span < timedelta(minutes=EXPIRED_MINUTES):
            return f"the calls that got it are less than {EXPIRED_MINUTES} minutes apart: resume once more later"
        return None

    def unreadable(self) -> str | None:
        """Why --unreadable does not take the order, or None when it does; the reason names the case of the last."""
        if not self._last("result_error"):
            return "its last stop is not result_error"
        read = self._span(lambda stop: _result_error(stop) and answered(stop))
        every = self._span(_result_error)
        if _apart(read, timedelta(minutes=EXPIRED_MINUTES)) or _apart(every, timedelta(hours=UNANSWERED_HOURS)):
            return None
        if answered(self.found[-1][0]):
            if read is None:
                return (f"one call only got an answer that could not be used: resume once more, {EXPIRED_MINUTES} "
                        "minutes or more later")
            return (f"the calls that got an answer that could not be used are less than {EXPIRED_MINUTES} minutes "
                    "apart: resume once more later")
        if every is None:
            return "one call only got that stop, with no usable answer: resume later"
        return ("the last call got no usable answer, and the calls that got that stop are less than "
                f"{UNANSWERED_HOURS} hours apart: resume later")

    def _last(self, kind: str) -> bool:
        return bool(self.found) and self.found[-1][0].get("kind") == kind

    def _span(self, kept: Callable[[dict], bool]) -> timedelta | None:
        """From the first kept stop with a time to the last, or None when they come from one call only."""
        seen = [(call, datetime.fromisoformat(stop["utc"])) for stop, call in self.found
                if kept(stop) and stop.get("utc")]
        if len({call for call, _ in seen}) < 2:
            return None
        return seen[-1][1] - seen[0][1]


def _apart(span: timedelta | None, least: timedelta) -> bool:
    return span is not None and span >= least
