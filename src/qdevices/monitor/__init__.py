"""`qdevices runs`, `jobs` and `usage`, read from records, with the tables of the last two. Reads only; no network."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .. import billing, older
from .. import record as records
from ..finder import AppRecords, OlderRecords, Unread, real, unique
from ..ledger import Ledger, Status
from ..resolve import DECISIONS, flag, joined
from .summary import Summary, init_jobs, short

if TYPE_CHECKING:
    from ..paths import Places

__all__ = ["Unread", "find", "init_jobs", "job_rows", "run_line", "summary", "usage"]


def find(places: "Places", cfg: dict, extra: Iterable[str | Path] = ()) -> list[Path | Unread]:
    """The records to read, each once, with an `Unread` for a folder or PATH that cannot be read."""
    found = AppRecords(Path(places.records)).listed()
    for site_config in cfg.values():
        for records_at in OlderRecords.listed_in(site_config):
            found += records_at.listed()
    for place in extra:
        found += OlderRecords(Path(place)).listed()      # a PATH as given: no ~ expanded
    return list(unique(found, key=lambda p: p if isinstance(p, Unread) else real(p)))


def summary(path: Path | Unread, decisions: older.Decisions | None = None) -> Summary | Unread:
    """The summary of one record, or the error line of a record or place that cannot be read."""
    if isinstance(path, Unread):
        return path
    try:
        lines = records.RecordLines.read(path)
    except records.RecordError as exc:
        return Unread(str(path), str(exc))
    try:
        return Summary.of(path, lines, decisions or older.Decisions())
    except (TypeError, ValueError, AttributeError, OverflowError) as exc:      # a value of a type the app never writes
        return Unread(str(path), f"a line holds a value of the wrong type ({type(exc).__name__})")


def run_line(s: Summary | Unread) -> str:
    """The line of a record in `qdevices runs`, or the error line of what cannot be read."""
    return f"{s.path}: {s.error}" if isinstance(s, Unread) else s.line()


HEAD: Final = (f"{'site':<9} {'project':<22} {'records':>7} {'jobs':>5} {'shots':>8} {'seconds':>9} {'counted':>9} "
        f"{'published':>9} {'init jobs':>9} {'init node s':>11}")
_NOTED: Final = ("stop", "refused", "failed", "not_submitted")        # the lines of an order that `jobs` shows below it


@dataclass(slots=True, kw_only=True)
class _Totals:
    """The sums of the records of one site and project, each added in a loop."""

    records: int = 0
    jobs: int = 0
    shots: int = 0
    seconds: float = 0.0
    published: float | None = None
    inits: int = 0
    init_seconds: float = 0.0
    counted: float = 0.0

    def add(self, s: Summary) -> None:
        """Add the counts and seconds of one record."""
        self.records += 1
        self.jobs += s.results
        self.shots += s.shots
        self.seconds += s.seconds
        self.counted += s.counted
        self.inits += s.init_jobs
        self.init_seconds += s.init_node_seconds
        if s.published is not None:
            self.published = (self.published or 0.0) + s.published

    def row(self, site: str, project: object) -> str:
        """The row of the totals in the table of `usage`."""
        published = "-" if self.published is None else f"{self.published:.1f}"
        return (f"{site:<9} {project:<22} {self.records:>7} {self.jobs:>5} {self.shots:>8} {self.seconds:>9.1f} "
                f"{self.counted:>9.1f} {published:>9} {self.inits:>9} {self.init_seconds:>11.1f}")


def usage(summaries: Iterable[Summary | Unread], cfg: dict) -> list[str]:
    """The lines of `qdevices usage`: the totals by site and project, the awards, what cannot be read, the notes."""
    summaries = list(summaries)
    totals: dict[tuple, _Totals] = {}
    for s in summaries:
        if not isinstance(s, Unread):
            totals.setdefault((str(s.site), str(s.project)), _Totals()).add(s)     # as text: any type sorts
    out = [HEAD, *(t.row(site, project) for (site, project), t in sorted(totals.items()))]
    out += _awards(totals, cfg)
    unread = [f"{s.path}: {s.error}" for s in summaries if isinstance(s, Unread)]
    out += unread + (["The records and folders above cannot be read: they are not in the totals."] if unread else [])
    measured, notes = billing.usage_words()
    out.append("These totals are read from the records found, not from the accounting of the sites. The seconds "
               f"are what each site measures: {measured}. The counted seconds put the seconds of a decision of "
               f"{_decisions()} in place of the measured ones.{notes}")
    return out


def _decisions() -> str:
    """The decisions that count seconds, as the usage note names them: `qdevices resolve --over-limit`, and so on."""
    first, *rest = map(flag, DECISIONS)
    return joined([f"`qdevices resolve {first}`", *(f"`{option}`" for option in rest)])


def _awards(totals: dict[tuple, _Totals], cfg: dict) -> list[str]:
    out = []
    for site, site_config in cfg.items():
        award = billing.award_seconds(site_config)
        if award is None:
            continue
        used = sum(t.seconds for (s, _), t in totals.items() if s == site)
        counted = sum(t.counted for (s, _), t in totals.items() if s == site)
        out.append(f"{site}: award {site_config['award_hours']} h = {award:,.0f} s; {used:,.1f} s measured in the "
                   f"records found ({_share(used, award)}), {counted:,.1f} s counted ({_share(counted, award)})")
    return out


def _share(seconds: float, award: float) -> str:
    return f"{100 * seconds / award:.2f} %" if award else "no share of an award of 0 h"


def job_rows(events: list[dict]) -> list[str]:
    """The lines of `qdevices jobs`: one for each order of a record, and its stops, refusals and failed rules."""
    ledger = Ledger(events)
    states, skipped = ledger.orders, ledger.skipped
    rows = [f"{'order':>5}  {'name':<12} {'id':<38} {'state':<22} {'shots':>6} {'seconds':>9}"]
    for order in sorted(set(states) | skipped):
        o = states.get(order)
        if o is None:
            rows.append(f"{order:>5}  {'-':<12} {'-':<38} {'skipped, never sent':<22}")
            continue
        last = [e.get("state") or e.get("status") or e.get("state_name") for e in events
                if e.get("event") == "status" and e.get("order") == order and not e.get("missed")]
        state = {Status.FINAL: o.final, Status.OPEN: f"open ({last[-1] if last else 'no state'})",
                 Status.LOST: "lost: resolve it", Status.UNSENT: "not sent"}[o.status]
        seconds = o.measured
        rows.append(f"{order:>5}  {o.name or '-'!s:<12} {o.id if o.id is not None else '-'!s:<38} "
                    f"{state:<22} {o.shots if o.shots is not None else '-'!s:>6} "
                    f"{'-' if seconds is None else f'{seconds:.3f}':>9}")
        noted = [e for e in events if e.get("order") == order
                 and (e.get("event") in _NOTED or (e.get("event") == "rule" and e.get("passed") is False))]
        rows += [f"{'':7}{e.get('event')}: {short(e.get('reason') or e.get('error') or e.get('text') or '-', 100)}"
                 for e in noted]
    return rows

