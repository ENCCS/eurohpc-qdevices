"""`qdevices resolve` on a record of this app: the "resolved" line goes into the record itself."""

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar, Final

from .. import record as records
from ..errors import Refused
from ..ledger import Ledger, Status
from ..sites import SITES
from ..sites.protocol import MADE_STATE
from ..values import in_url
from .resolution import Case, Resolution, Said
from .stops import EXPIRED_MINUTES, UNANSWERED_HOURS, Stops

_NEW_DAYS: Final = 3
_READ_HOURS: Final = 24


def two_step_titles() -> str:
    """The titles of the sites that make a job before they submit it, joined, with a space after; "" for none."""
    titles = ", ".join(cls.profile.title for cls in SITES.values() if cls.made_step is not None)
    return f"{titles} " if titles else ""


@dataclass(slots=True, kw_only=True)
class AppResolution(Resolution):
    """A resolve of an order of a record of this app."""

    @staticmethod
    def owns(path: Path, events: list[dict], records_root: Path) -> bool:
        """True for a record of this app: by its start line, or by name below the records folder, as a send reads it."""
        real = Path(path).resolve()
        return Ledger(events).is_app or (Path(records_root).resolve() in real.parents
                                         and records.NAME.fullmatch(real.name) is not None)

    def site(self) -> str:
        """The site the record names; --gone is refused, as it is for a record of another runner."""
        if self.job_id is not None and not (self.job_id and in_url(self.job_id)):
            raise Refused(f"{self.path}: --job {self.job_id!r} is empty or cannot be put in a URL as it is")
        if self.decision == "gone":
            raise Refused(f"{self.path} is a record of this app: --gone is only for a record of another runner. "
                          "Here an open order whose result the site no longer gives is resolved with --expired")
        site = Ledger(self.events).site
        if site is None:
            raise Refused(f"{self.path} names no site this app knows")
        return site

    def target(self, case: Case) -> tuple[Path, dict]:
        """The record itself, with its site and project."""
        return self.path, {"app": "qdevices", "site": case.site, "project": Ledger(case.lines).project}

    def line(self, case: Case, fields: dict) -> dict:
        """The order fields first for a decision; the fields of --job and --none before them, the id of its type."""
        where = {"order": self.order, "name": case.order.name, "by_host": self.host}
        if self.decision is not None:
            return {**where, **fields}
        return {**({"id": self._job(case)} if "id" in fields else fields), **where}     # with the record open

    def said(self, text: str, target: Path) -> str:
        """What the decision says."""
        return text

    def _job_or_none(self, case: Case) -> tuple[dict, Said]:
        o, status = case.order, case.status
        unknown = status == Status.OPEN and bool(o.stops) and o.stops[-1][0] == "submit_unknown"
        stuck = self._stuck(case)
        why = self._still_new(case.events) if status == Status.OPEN and not unknown else "not open"
        new = why is None
        if status != Status.LOST and not unknown and not new and not stuck:
            raise Refused(f"{self._where} is {status}, not lost: with --job or --none only a lost order, an open "
                          f"{two_step_titles()}order whose last stop is submit_unknown, or an open order that the "
                          f"site showed only as New for {_NEW_DAYS} days or more and still New in the last "
                          f"{_READ_HOURS} h, is resolved" + ("" if status != Status.OPEN else f" ({why})"))
        if unknown and self.job_id is not None:
            made = SITES[case.site].profile.configuring_state or MADE_STATE
            raise Refused(f"{self._where} has the job {o.id} already. When the site shows it past {made}, a resume "
                          "collects it; when the site shows that it never ran, give --none")
        if new and self.job_id is not None:
            raise Refused(f"{self._where} has the job {o.id} already, still New: only --none is taken")
        return self._taken(case, unknown, new, stuck)

    def _stuck(self, case: Case) -> bool:
        # An id no URL holds: no read of its state can name its job, and a job may exist.
        if case.status == Status.OPEN:
            return not in_url(str(case.order.id))
        return case.status == Status.LOST and any(e.get("event") == "stop" and e.get("order") == self.order
                                                  and e.get("id_no_url") is True for e in case.events)

    def _taken(self, case: Case, unknown: bool, new: bool, stuck: bool) -> tuple[dict, Said]:
        o, order = case.order, self.order
        if self.job_id is None and new:
            return ({"none": True, "still_new": True}, f"order {order} is final: the job {o.id} stayed New at the "
                    "site; it is not cancelled, and it counts at the job time limit")
        if self.job_id is None and stuck:
            return ({"none": True, "stuck": True}, f"order {order} is final: the site gave a job id that no URL can "
                    "hold, so a job may exist; it is not cancelled, and it counts at the job time limit")
        if self.job_id is None:
            return {"none": True}, (f"order {order} is final: the job {o.id} never ran, as you found; it is not "
                                    "cancelled" if unknown else f"order {order} is final with no job")
        return {"id": self.job_id}, lambda line: f"order {order} has the job {line['id']}; a resume collects it"

    def _job(self, case: Case) -> int | str:
        if SITES[case.site].profile.numeric_ids and self.job_id.isascii() and self.job_id.isdigit():
            with contextlib.suppress(ValueError):       # more digits than int reads: kept as text, as any text is
                return int(self.job_id)
        return self.job_id

    def _expired(self, case: Case) -> tuple[dict, str]:
        rule = f"result_expired, after two calls {EXPIRED_MINUTES} minutes or more apart got that answer"
        return self._at_limit(case, "expired", rule, Stops.expired, "the site does not give its result")

    def _unreadable(self, case: Case) -> tuple[dict, str]:
        rule = (f"result_error, after two calls {EXPIRED_MINUTES} minutes or more apart got an answer that could not "
                f"be used, or two calls {UNANSWERED_HOURS} hours or more apart got that stop")
        return self._at_limit(case, "unreadable", rule, Stops.unreadable,
                              "the site shows the job finished, and its result cannot be read")

    def _at_limit(self, case: Case, key: str, rule: str, why_not: Callable[[Stops], str | None],
                  cause: str) -> tuple[dict, str]:
        """An open order whose stops meet the rule of the decision: final, counted at the job time limit."""
        why = why_not(Stops.of(case.lines, self.order)) if case.status == Status.OPEN else "it is not open"
        if why is not None:
            raise Refused(f"{self._where} is {case.status}: --{key} takes only an open order whose last stop is "
                          f"{rule} ({why})")
        return ({key: True, "counted_seconds": case.limit},
                f"{self._where} is final: {cause}; it is never sent again, and it counts at {case.limit:.0f} s")

    def _still_new(self, events: list[dict]) -> str | None:
        now = self.clock.utc()
        states = [(e.get("state"), datetime.fromisoformat(e["utc"])) for e in events
                  if e.get("event") == "status" and e.get("order") == self.order and e.get("utc")
                  and not e.get("missed")]
        if not states:
            return "it has no status line"
        other = sorted({state for state, _ in states if state != "New"}, key=str)
        if other:
            return f"the site showed it as {', '.join(map(str, other))}"
        if now - states[0][1] < timedelta(days=_NEW_DAYS):
            return f"it is New for less than {_NEW_DAYS} days"
        if now - states[-1][1] > timedelta(hours=_READ_HOURS):
            return f"its last read is older than {_READ_HOURS} h: read it once more with a resume"
        return None

    TAKES: ClassVar = MappingProxyType({None: _job_or_none, "over_limit": Resolution._over_limit,
                                        "expired": _expired, "unreadable": _unreadable})
