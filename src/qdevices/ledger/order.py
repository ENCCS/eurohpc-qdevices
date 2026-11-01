"""One order of a record: what its lines say, folded by their kind, and the seconds it counts with."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

from .kinds import AT_LIMIT, NEVER_SUBMITTED, Outcome, Status, job_id, number, seconds_of


@dataclass(slots=True, kw_only=True)
class Order:
    """What a record says of one order; it changes only while its lines are folded."""

    order: int
    name: Any = None
    asked: bool = False
    id: Any = None
    submitted: bool = False
    final: Outcome | None = None
    result: dict | None = None
    stops: list[tuple] = field(default_factory=list)
    shots: Any = None
    counted: float | None = None

    def apply(self, e: dict) -> None:
        """One line of this order folded in: its name, its shots, then the handler of its kind."""
        if e.get("name"):
            self.name = e["name"]
        if e.get("shots") is not None:
            self.shots = e["shots"]
        if not isinstance(e["event"], str):     # a line the app never writes: as if asked, so never sent again
            self.asked = True
        elif handler := _ON.get(e["event"]):
            handler(self, e)

    def settle(self) -> None:
        """The last step of the fold: a job made and never submitted, by the stops of its record, is final."""
        if self.final is None and self.id is not None and not self.submitted and self.stops:
            unanswered = any(kind == "submit_error" and not (isinstance(code, int) and 400 <= code < 500)
                             for kind, code in self.stops)
            if self.stops[-1][0] in NEVER_SUBMITTED and not unanswered:
                self.final = Outcome.NEVER_SUBMITTED

    @property
    def status(self) -> Status:
        """Final, open, lost or unsent, by what the lines say."""
        if self.final:
            return Status.FINAL
        if self.id is not None:
            return Status.OPEN
        return Status.LOST if self.asked else Status.UNSENT

    @property
    def measured(self) -> float | None:
        """The seconds of its result line, of any final kind: a failed line after it does not hide them."""
        return seconds_of(self.result) if self.result else None

    @property
    def counted_seconds(self) -> float | None:
        """The seconds an order counts with: those of a resolve decision, else the measured seconds of its result."""
        return self.counted if self.counted is not None else self.measured

    def budget(self, job_limit: float) -> float:
        """The seconds of the budget it uses: an upper bound, at the job time limit where the time is not known."""
        if self.counted is not None:
            return max(self.counted, 0.0)
        if self.final == Outcome.RESULT:
            seconds = self.measured
            return job_limit if seconds is None else max(seconds, 0.0)
        if self.final in AT_LIMIT or self.status in (Status.OPEN, Status.LOST):
            return job_limit
        return 0.0

    def _asked(self, _e: dict) -> None:
        self.asked = True

    def _take_id(self, e: dict) -> None:
        if (found := job_id(e)) is not None:
            self.id = found

    def _submitted(self, e: dict) -> None:
        self.asked = True
        self._take_id(e)
        if e.get("step") in (None, "submitted"):    # an older runner's step "created" is not a submission
            self.submitted = True

    def _resolved(self, e: dict) -> None:
        if "start_sha256" in e and not self._holds(e):
            return
        if e.get("none"):
            self.final = (Outcome.RESOLVED_NEW if e.get("still_new") else
                          Outcome.RESOLVED_STUCK if e.get("stuck") else Outcome.RESOLVED_NONE)
        elif e.get("expired"):
            self.final, self.counted = Outcome.RESOLVED_EXPIRED, number(e.get("counted_seconds"))
        elif e.get("gone"):
            self.final, self.counted = Outcome.RESOLVED_GONE, number(e.get("counted_seconds"))
        elif e.get("over_limit"):
            self.counted = number(e.get("counted_seconds"))
        elif e.get("id") is not None:
            self.id = e["id"]

    def _holds(self, e: dict) -> bool:
        # True while an order is still as a decision on an older record found it.
        if e.get("none"):
            return self.id is None and self.final is None
        if e.get("gone"):
            return self.final is None and self.id == e.get("decided_id")
        if e.get("over_limit"):
            return self.final == Outcome.RESULT and self.id == e.get("decided_id")
        return False

    def _expired(self, _e: dict) -> None:
        self.final = self.final or Outcome.EXPIRED      # an older runner's line; a result read before it stands

    def _result(self, e: dict) -> None:
        self.final, self.result = Outcome.RESULT, e

    def _ended(self, e: dict) -> None:
        self.final = Outcome(e["event"])

    def _stop(self, e: dict) -> None:
        self.stops.append((e.get("kind"), e.get("http_status")))


_ON: Final[Mapping[str, Callable[[Order, dict], None]]] = MappingProxyType({
    "submitting": Order._asked,
    "step": Order._take_id,
    "submitted": Order._submitted,
    "resolved": Order._resolved,
    "expired": Order._expired,
    "result": Order._result,
    "refused": Order._ended,
    "refusal": Order._ended,
    "failed": Order._ended,
    "not_submitted": Order._ended,
    "stop": Order._stop,
})
