"""`qdevices resolve` on a record of another runner: the line goes into the decisions file of its site."""

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar

from .. import older
from .. import record as records
from ..errors import Refused
from ..finder import OlderRecords
from ..ledger import Ledger, Status
from ..sites import SITES
from .resolution import Case, Resolution


@dataclass(slots=True, kw_only=True)
class OtherResolution(Resolution):
    """A resolve of an order of a record of another runner, which is never written."""

    def site(self) -> str:
        """The one site whose older_records hold the record and read it; the config is read here, once."""
        if self.job_id is not None or self.decision == "expired":
            raise Refused(f"{self.path} is a record of another runner: the app does not collect it, so --job and "
                          "--expired are not taken (collect it with that runner). --gone takes an open order whose "
                          "job the site no longer gives")
        self.cfg = self._config()
        site = self._site_for()
        self._starts(self.events)
        return site

    def decided(self, site: str, events: list[dict]) -> list[dict]:
        """The lines of the record, then the decisions of the site made on them."""
        try:
            decisions = older.Decisions.load(self.places.records, (site,))
        except records.RecordError as exc:
            raise Refused(str(exc)) from None
        self._starts(events)
        return decisions.merged(events)

    def target(self, case: Case) -> tuple[Path, dict]:
        """The decisions file of the site."""
        return older.Decisions.file(self.places.records, case.site), {"app": "qdevices", "site": case.site}

    def line(self, case: Case, fields: dict) -> dict:
        """The order fields, the binding to the lines read, the job id and the real path, then the decision."""
        return {"order": self.order, "name": case.order.name, "by_host": self.host,
                **older.binding(case.events), "decided_id": case.order.id,
                "record": str(self.path.resolve()), **fields}

    def said(self, text: str, target: Path) -> str:
        """The decision, and where it is."""
        return f"{text}. The decision is in {target}; the record of the other runner is not written"

    def _site_for(self) -> str:
        real, own = self.path.resolve(), Ledger(self.events).site
        holding = [site for site in SITES if any(self._holds(place, real) for place in self.cfg[site]["older_records"])]
        reading = [site for site in holding if own in (None, site)]
        if len(reading) > 1:
            raise Refused(f"{self.path} names no site, and the older_records of {' and '.join(reading)} hold it: a "
                          "decision on it is for one site, so list it for one site only")
        if not reading:
            whose = f" for {own}" if own else ""
            held = (f"only the older_records of {' and '.join(holding)} hold it" if holding
                    else "no older_records in qdevices.toml hold it")
            raise Refused(f"{self.path} is a record of another runner{whose}, and {held}. List it, or its folder, in "
                          f"older_records of {own or 'its site'} first: a decision on a record the app does not read "
                          "has no effect")
        return reading[0]

    @staticmethod
    def _holds(place: str, real: Path) -> bool:
        try:
            return real in {p.resolve() for p in OlderRecords.at(place).files()}
        except (records.RecordError, OSError, RuntimeError):
            return False              # no record a send could read

    def _starts(self, events: list[dict]) -> None:
        if older.start_digest(events) is None:
            raise Refused(f"the first line of {self.path} is not a start line: a decision cannot be tied to the "
                          "record, so the app would never read it")

    def _gone(self, case: Case) -> tuple[dict, str]:
        if case.status != Status.OPEN:
            raise Refused(f"{self._where} is {case.status}: --gone takes only an open order, with a job id and no "
                          "final line, whose job the site no longer gives")
        return ({"gone": True, "counted_seconds": case.limit},
                f"{self._where} is final: the site no longer gives the job {case.order.id}; it counts at "
                f"{case.limit:.0f} s")

    def _none(self, case: Case) -> tuple[dict, str]:
        if case.status != Status.LOST:
            raise Refused(f"{self._where} is {case.status}: in a record of another runner --none takes only a lost "
                          "order, with a 'submitting' line and no job id"
                          + ("; for an open order whose job the site no longer gives, give --gone"
                             if case.status == Status.OPEN else ""))
        return {"none": True}, f"{self._where} is final with no job"

    TAKES: ClassVar = MappingProxyType({None: _none, "over_limit": Resolution._over_limit, "gone": _gone})
