"""The words for the state of an order, and what one line of a record gives: its job id and its seconds."""

from enum import StrEnum
from typing import Any, Final

from ..values import is_number

ID_KEYS: Final = ("id", "uuid", "job", "uid")
NEVER_SUBMITTED: Final = ("upload_error", "not_submitted")  # stop kinds of older runners; a tuple: a kind may be a list


class Status(StrEnum):
    """Where an order stands, by the lines of its record."""

    FINAL = "final"
    OPEN = "open"
    LOST = "lost"
    UNSENT = "unsent"


class Outcome(StrEnum):
    """The 12 ways an order is final."""

    RESULT = "result"
    REFUSED = "refused"
    REFUSAL = "refusal"
    FAILED = "failed"
    NOT_SUBMITTED = "not_submitted"
    EXPIRED = "expired"
    NEVER_SUBMITTED = "never_submitted"
    RESOLVED_NONE = "resolved_none"
    RESOLVED_NEW = "resolved_new"
    RESOLVED_STUCK = "resolved_stuck"
    RESOLVED_EXPIRED = "resolved_expired"
    RESOLVED_GONE = "resolved_gone"


AT_LIMIT: Final = frozenset({Outcome.FAILED, Outcome.EXPIRED, Outcome.RESOLVED_NEW, Outcome.RESOLVED_STUCK,
                             Outcome.RESOLVED_EXPIRED, Outcome.RESOLVED_GONE})      # final, time not known


def job_id(event: dict) -> Any:
    """The job id of a line: the value of the first key of ID_KEYS that is not None; else None."""
    for key in ID_KEYS:
        if event.get(key) is not None:
            return event[key]
    return None


def number(value: object) -> float | None:
    """A number read from a line, as a float; None for a bool, NaN, an int beyond the floats or any other value."""
    if is_number(value) and value == value:
        try:
            return float(value)
        except OverflowError:
            return None
    return None


def seconds_of(result: dict) -> float | None:
    """The seconds a result line holds: this app's "seconds", or the keys of the older runners."""
    for key in ("seconds", "device_seconds", "wall_seconds"):
        value = number(result.get(key))
        if value is not None:
            return value
    return None
