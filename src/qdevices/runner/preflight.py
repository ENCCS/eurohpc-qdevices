"""The checks of a call that sends, before its record is opened. They read config and records only."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .. import older
from .. import record as records
from ..config import project_problems
from ..errors import Refused
from ..finder import AppRecords, OlderRecords, real, unique
from ..ledger import Ledger

if TYPE_CHECKING:
    from ..paths import Places


def check_stage(*, max_order: int | None, resume: Path | None, new_run: bool, new_rules: bool = False) -> None:
    """Refused for a call that names no stage, or two that do not go together."""
    if max_order is None and resume is None:
        raise Refused("a live call needs --max-order N or --resume FILE; nothing is sent")
    if resume is not None and new_run:
        raise Refused("--new-run starts a new record; it does not go with --resume")
    if resume is None and new_rules:
        raise Refused("--new-rules goes with --resume: a new record is held to the rules file of its own call")


def check_arguments(man: dict, site, cfg: dict, *, max_order: int | None) -> dict:
    """The config of the site, or Refused for a call that must not start. No site and no record is read."""
    if man["site"] != site.name:
        raise Refused(f"the manifest is for {man['site']}, the site object is {site.name}")
    if max_order is not None and not 1 <= max_order <= len(man["jobs"]):
        raise Refused(f"--max-order {max_order}: the manifest has the orders 1 to {len(man['jobs'])}")
    site_config = cfg[site.name]
    if max_order is not None:
        problems = project_problems(man, site_config)
        if site_config["budget_seconds"] is None:
            problems.append(f"no budget_seconds for {site.name} in qdevices.toml: the budget rule needs it")
        if problems:
            raise Refused("; ".join(problems))
    if site_config["window"]:
        try:
            ZoneInfo(site_config["window_zone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise Refused(f"the window zone {site_config['window_zone']!r} is not known") from None
    return site_config


class Scan(NamedTuple):
    """One record of a site as a send reads it; for an older one, with its decisions."""

    path: Path
    ledger: Ledger
    older: bool


@dataclass(frozen=True, slots=True)
class SiteScan:
    """Every record of a site, those of this app, then those of the older folders of the config."""

    scans: list[Scan] = field(default_factory=list)

    @classmethod
    def read(cls, places: "Places", site: str, site_config: dict) -> Self:
        """The records of a site; a record or decisions file that cannot be read raises RecordError."""
        decisions = older.Decisions.load(places.records, (site,)) if site_config["older_records"] else older.Decisions()
        found = [(path, False) for path in AppRecords(Path(places.records) / site).files()]
        for records_at in OlderRecords.listed_in(site_config):
            found += [(path, True) for path in records_at.files()]
        scans = []
        for path, is_older in unique(found, key=lambda item: real(item[0])):
            events = records.RecordLines.read(path).events
            if not is_older or Ledger(events).site in (None, site):      # the site of the record's own lines
                scans.append(Scan(path, Ledger(decisions.merged(events) if is_older else events), is_older))
        return cls(scans)

    @classmethod
    def readable(cls, places: "Places", site: str, site_config: dict) -> Self:
        """The records of a site, with a record that cannot be read as a refusal of the call."""
        try:
            return cls.read(places, site, site_config)
        except records.RecordError as exc:
            raise Refused(f"{exc}. A call that sends needs every record of the site readable: the budget and "
                          "the open-order check read them all") from None

    def blockers(self) -> list[str]:
        """The orders, in any record of the site, that are open or lost."""
        return [f"{s.path}: order {order} is {status}" for s in self.scans for order, status in s.ledger.open_or_lost]

    def used_elsewhere(self, here: Path, project: str, job_limit: float) -> float:
        """The seconds used by the other records of the site: older ones, and this app's of the same project."""
        return sum(s.ledger.used_seconds(job_limit) for s in self.scans
                   if s.path.resolve() != here and (s.older or s.ledger.first("project") == project))
