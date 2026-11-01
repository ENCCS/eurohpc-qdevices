"""The summary of one record: its counts and seconds, and its line in `qdevices runs`."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Self

from .. import billing, older
from ..ledger import Ledger, Outcome, Status, seconds_of
from ..record import RecordLines
from ..sites.protocol import INIT_CREATED, INIT_JOB, INIT_STATUS, NODE_SECONDS

_SHORT: Final = 70


def _utc(text: Any) -> str:
    """A time stamp to the second, with Z; "-" for none."""
    return "-" if not text else str(text)[:19] + "Z"


def short(text: Any, width: int = _SHORT) -> str:
    """A text on one line, cut to a width with "..." at its end."""
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[:width - 3] + "..."


def init_jobs(events: list[dict]) -> tuple[int, float, int]:
    """The init jobs of a record: how many, their node seconds where known, and how many have none."""
    ids, seconds = set(), {}
    for e in events:
        if e.get("event") != "init":
            continue
        if e.get("step") == INIT_CREATED and e.get(INIT_JOB) is not None:
            ids.add(e[INIT_JOB])
        elif e.get("step") == "created" and e.get("job") is not None:      # an older runner
            ids.add(e["job"])
        if e.get("step") == INIT_STATUS and isinstance(e.get(NODE_SECONDS), (int, float)):
            seconds[e.get(INIT_JOB)] = float(e[NODE_SECONDS])
    return len(ids), round(sum(seconds.values()), 3), len(ids - set(seconds))


@dataclass(frozen=True, slots=True, kw_only=True)
class Summary:
    """The counts and seconds of one record. The site, the start and the project come from its own lines."""

    path: str
    site: str
    project: Any
    run: str
    manifest_jobs: Any
    results: int
    shots: int
    seconds: float
    no_seconds: int
    counted: float
    decided: int
    published: float | None
    init_jobs: int
    init_node_seconds: float
    init_no_seconds: int
    open: list[tuple[int, Status]]
    cut_lines: int
    last: str
    first_utc: str | None
    last_utc: str | None

    @classmethod
    def of(cls, path: Path, lines: RecordLines, decisions: older.Decisions) -> Self:
        """The summary of the lines of a record; an older record has its decisions after its lines."""
        events, own = lines.events, Ledger(lines.events)
        site = own.site or "unknown"
        merged = Ledger(decisions.merged(events))
        results, seconds, decided, counted = cls._orders(merged)
        start = own.start or {}
        stamps = [e["utc"] for e in events if e.get("utc")]
        inits, init_seconds, init_unknown = init_jobs(events)
        published = [billing.published_seconds(site, r.get("shots") or 0)
                     for r, s in zip(results, seconds, strict=True) if s is not None]
        return cls(path=str(path), site=site, project=own.project or "-",
                   run=start.get("run") or Path(start.get("lists") or path.parent).name,
                   manifest_jobs=len(start["jobs"]) if isinstance(start.get("jobs"), list) else start.get("jobs"),
                   results=len(results), shots=sum(r.get("shots") or 0 for r in results),
                   seconds=round(sum(s for s in seconds if s is not None), 3), no_seconds=seconds.count(None),
                   counted=round(sum(s for s in counted if s is not None), 3), decided=len(decided),
                   published=round(sum(p for p in published if p is not None), 3) if billing.publishes(site) else None,
                   init_jobs=inits, init_node_seconds=init_seconds, init_no_seconds=init_unknown,
                   open=merged.open_or_lost, cut_lines=len(lines.cut), last=cls._last_call(events),
                   first_utc=min(stamps, default=None), last_utc=max(stamps, default=None))

    def line(self) -> str:
        """The line of the record in `qdevices runs`."""
        return f"{self.site}  {self.project}  {self.run}  {self.path}: " + "; ".join(self._parts())

    @staticmethod
    def _orders(merged: Ledger) -> tuple[list[dict], list, list, list]:
        orders = merged.orders.values()
        results = [o.result for o in orders if o.final == Outcome.RESULT and not o.result.get("refused")]
        seconds = [seconds_of(r) for r in results]
        decided = [o for o in orders if o.counted is not None]
        counted = [o.counted_seconds for o in orders
                   if o.counted is not None or (o.final == Outcome.RESULT and not o.result.get("refused"))]
        return results, seconds, decided, counted

    @staticmethod
    def _last_call(events: list[dict]) -> str:
        begins = [i for i, e in enumerate(events) if e.get("event") in ("start", "resume")]
        tail = events[begins[-1]:] if begins else events
        for kind in ("stop", "end"):
            found = [e for e in tail if e.get("event") == kind]
            if found:
                return f"{kind}: {found[-1].get('reason') or 'no reason given'}"
        return "in progress, or cut off"

    def _parts(self) -> list[str]:
        jobs = self.manifest_jobs if self.manifest_jobs is not None else "-"
        parts = [f"{self.results} results of {jobs} jobs", f"{self.seconds:.1f} s measured"]
        if self.decided:
            parts.append(f"{self.counted:.1f} s counted ({self.decided} orders resolved over the limit or expired)")
        if self.no_seconds:
            parts.append(f"{self.no_seconds} results with no seconds")
        if self.published is not None:
            parts.append(f"{self.published:.1f} s by the published rule")
        if self.init_jobs:
            parts.append(f"{self.init_jobs} init jobs")
        if self.open:
            parts.append("open or lost: " + ", ".join(f"order {o} {status}" for o, status in self.open))
        if self.cut_lines:
            parts.append(f"{self.cut_lines} cut lines")
        return [*parts, f"{_utc(self.first_utc)} to {_utc(self.last_utc)}", short(self.last)]
