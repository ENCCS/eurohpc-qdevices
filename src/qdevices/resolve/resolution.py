"""The template of one `qdevices resolve`: checks before the lock, then the second read, a decision and one line."""

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Final, TypeAlias

from .. import config as configs
from .. import record as records
from ..clock import Clock
from ..errors import Refused
from ..ledger import Ledger, Order, Outcome, Status
from ..lock import Locks, TakeLock
from ..paths import Places

_NOT_IN_RECORD: Final = "not in the record"       # the status of an order that no line names
Said: TypeAlias = str | Callable[[dict], str]     # what a decision says, or that text made from its written line


@dataclass(frozen=True, slots=True, kw_only=True)
class Case:
    """What the read under the lock gives a decision: its lines, the order, its status and the job time limit."""

    site: str
    events: list[dict]                # the lines of the record
    lines: list[dict]                 # those lines, then the decisions made on them for a record of another runner
    order: Order | None
    status: Status | str              # a Status, or _NOT_IN_RECORD
    limit: float | None               # job_seconds_limit, read only for a decision


@dataclass(slots=True, kw_only=True)
class Resolution(ABC):
    """A resolve of one order. The decision and its line read only the lines read again under the lock."""

    TAKES: ClassVar[Mapping[str | None, Callable[["Resolution", Case], tuple[dict, Said]]]]

    path: Path
    order: int
    job_id: str | None
    decision: str | None
    places: Places
    clock: Clock
    host: str
    take_lock: TakeLock | None
    cfg: dict | None
    events: list[dict]                # the read before the lock, only to find the site

    def run(self) -> str:
        """The checks, then under the lock of the site the second read, the decision and its one synced line."""
        site = self.site()
        locks = Locks(self.places.state, host=self.host, started=self.clock.utc().isoformat())
        with locks.held(site, take=self.take_lock):
            with self._typed():
                case = self._case(site)
            take = self.TAKES.get(self.decision)
            if take is None:
                raise ValueError(f"no decision {self.decision!r}")
            with self._typed():
                fields, said = take(self, case)
            target, base = self.target(case)
            with records.Record(target, self.clock, base) as rec:
                written = rec.write("resolved", **self.line(case, fields))
            return self.said(said(written) if callable(said) else said, target)

    @abstractmethod
    def site(self) -> str:
        """The site whose lock the resolve takes; Refused when the record or the decision is not for one."""

    @staticmethod
    def read(path: Path) -> list[dict]:
        """The lines of a record: read once to find its site, then again under the lock; Refused when unreadable."""
        try:
            return records.RecordLines.read(path).events
        except records.RecordError as exc:          # not there, or removed or changed since the first read
            raise Refused(str(exc)) from None

    def decided(self, site: str, events: list[dict]) -> list[dict]:
        """The lines the decision is made on: those of the record, as no decisions file holds decisions on them."""
        return events

    @abstractmethod
    def target(self, case: Case) -> tuple[Path, dict]:
        """The file the line goes into, and the fields that open each of its lines."""

    @abstractmethod
    def line(self, case: Case, fields: dict) -> dict:
        """The fields of the "resolved" line, in their order, from those of the decision."""

    @abstractmethod
    def said(self, text: str, target: Path) -> str:
        """What the call says once the line is on disk."""

    @contextmanager
    def _typed(self) -> Iterator[None]:
        """A line of the record with a value of a type this app never writes: a refusal, before anything is written."""
        try:
            yield
        except (TypeError, ValueError, AttributeError, OverflowError) as exc:
            raise Refused(f"{self.path} cannot be read: a line holds a value of the wrong type "
                          f"({type(exc).__name__}: {exc})") from None

    def _case(self, site: str) -> Case:
        events = self.read(self.path)
        lines = self.decided(site, events)
        o = Ledger(lines).orders.get(self.order)
        limit = self._limit(site) if self.decision is not None else None
        return Case(site=site, events=events, lines=lines, order=o, status=o.status if o else _NOT_IN_RECORD,
                    limit=limit)

    def _config(self) -> dict:
        return configs.load(self.places.config) if self.cfg is None else self.cfg

    def _limit(self, site: str) -> float:
        return float(self._config()[site]["job_seconds_limit"])

    @property
    def _where(self) -> str:
        return f"order {self.order} of {self.path}"

    def _over_limit(self, case: Case) -> tuple[dict, str]:
        o, limit = case.order, case.limit
        why = self._beyond(o, limit) if o else "it has no line"
        if why is not None:
            raise Refused(f"{self._where} is {case.status}: --over-limit takes only a final order whose result has "
                          f"more seconds than job_seconds_limit ({why})")
        measured = o.measured
        return ({"over_limit": True, "measured_seconds": measured, "counted_seconds": limit},
                f"{self._where} counts at {limit:.0f} s from now on; its {measured:.1f} s measured stay in the record")

    @staticmethod
    def _beyond(o: Order, limit: float) -> str | None:
        seconds = o.measured if o.final == Outcome.RESULT else None
        if seconds is None:
            return "it has no result with seconds"
        if o.counted is not None:
            return "it is resolved already"
        if seconds <= limit:
            return f"its {seconds:.1f} s are within job_seconds_limit, {limit:.0f} s"
        return None
