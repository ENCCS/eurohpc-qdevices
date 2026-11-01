"""A stop of a call: its kind with an exit code, the exception that ends the call, and what was under way."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Self


class StopKind(StrEnum):
    """The kind of a stop line, with the exit code of the call it ends."""

    code: int

    def __new__(cls, text: str, code: int) -> Self:
        """A member: its text, and the exit code that goes with it."""
        member = str.__new__(cls, text)
        member._value_ = text
        member.code = code
        return member

    READ = "read", 1
    CHECK = "check", 1
    PREPARE = "prepare", 1
    LOST = "lost", 1
    STATUS_ERROR = "status_error", 1
    RESULT_ERROR = "result_error", 1
    RESULT_EXPIRED = "result_expired", 1
    SUBMIT_UNKNOWN = "submit_unknown", 1
    UNKNOWN = "unknown", 2
    RULE = "rule", 2
    TIMEOUT = "timeout", 2
    ERROR = "error", 3
    INTERRUPT = "interrupt", 130


class Stopped(BaseException):
    """The end of a call at a stop; a BaseException, so no except Exception lets it go on; only the Loop catches it."""

    def __init__(self, kind: StopKind) -> None:
        super().__init__(kind.value)
        self.kind = kind


@dataclass(slots=True, kw_only=True)
class UnderWay:
    """The request or wait under way, which a stop at an interrupt or an error must name."""

    order: int | None = None
    name: str | None = None
    phase: str | None = None
    held: dict[str, Any] = field(default_factory=dict)    # "init_job" and "id" in the order they came; None kept

    def fields(self) -> dict:
        """Its fields for a stop line: the order, its name and the phase if given, then the ids held."""
        given = {"order": self.order, "name": self.name, "phase": self.phase}
        return {**{key: value for key, value in given.items() if value is not None}, **self.held}

    @property
    def text(self) -> str:
        """The sentence of a stop that names the job or init job under way; "" for none."""
        ids = [f"{what} {self.held[key]}" for key, what in (("id", "job"), ("init_job", "init job"))
               if self.held.get(key) is not None]
        return f"Under way at the stop: order {self.order} ({self.name}), {' and '.join(ids)}." if ids else ""
