"""The record of a call: what every opening shares, and a new record after the checks of the site."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from os import stat_result
from pathlib import Path

from .. import __version__
from .. import record as records
from ..clock import stamp
from ..errors import Refused
from ..redact import redact
from ..screen import quoted
from ..sites import SITES
from .preflight import SiteScan
from .rulesfile import RulesFile


@dataclass
class Opened:
    """The record of this call, the lines it held before, and every record of the site (for a send)."""

    rec: records.Record
    prior: list[dict] = field(default_factory=list)
    site_scan: SiteScan = field(default_factory=SiteScan)
    rules_path: str | None = None
    tell: Callable[[], None] = lambda: None     # its first texts, said in the loop, so an interrupt has its stop line


@dataclass
class Opening(ABC):
    """What a call needs to open its record; a subclass gives the opening of its kind."""

    man: dict
    site: object
    site_config: dict
    places: object
    clock: object
    host: str
    max_order: int | None
    say: object
    rules_file: RulesFile             # this call's rules file
    new_rules: bool

    def __post_init__(self) -> None:
        shown = self.say
        self.say = lambda text="": shown(redact(text, self.site.secrets()))     # the token filter on the screen

    @property
    def sending(self) -> bool:
        """True for a call that may send, up to its max order."""
        return self.max_order is not None

    @property
    def run_dir(self) -> Path:
        """The run folder of the manifest at its site."""
        return Path(self.places.records) / self.site.name / self.man["run"]

    def base(self) -> dict:
        """The fields of every line of the record: the route keys of its site come after project."""
        man = self.man
        base = {"app": "qdevices", "site": self.site.name, "machine": man["machine"], "project": man["project"]}
        base.update((key, man[key]) for key, _ in SITES[self.site.name].profile.route_keys)
        return base

    def files(self) -> dict:
        """The SHA-256 of the file of each order, by its order as a text."""
        return {str(j["order"]): j["sha256"] for j in self.man["jobs"]}

    def record(self, path: Path) -> records.Record:
        """The record at a path, with the fields of every line and the secrets of the site."""
        return records.Record(path, self.clock, self.base(), self.site.secrets)

    @staticmethod
    def _identity(real: Path, info: stat_result) -> dict:
        return {"path": str(real), "device": info.st_dev, "inode": info.st_ino}

    def open(self) -> Opened:
        """The record of this call; a call that only collects reads no other record."""
        site_scan = SiteScan.readable(self.places, self.site.name, self.site_config) if self.sending else SiteScan()
        return self._open(site_scan)

    @abstractmethod
    def _open(self, site_scan: SiteScan) -> Opened: ...


@dataclass(kw_only=True)
class NewRecord(Opening):
    """A new record, after the check that no record of the site has an open or lost order."""

    new_run: bool

    def _open(self, site_scan: SiteScan) -> Opened:
        self._check(site_scan)
        path = self.run_dir / f"run_{stamp(self.clock.utc())}.jsonl"
        if path.exists():
            raise Refused(f"{path} exists already; start again in a second")
        rec = self.record(path)
        real = path.resolve()
        info = real.stat()
        man = self.man
        jobs = [{k: v for k, v in j.items() if k != "text"} for j in man["jobs"]]
        rec.write("start", version=__version__, host=self.host, record=self._identity(real, info),
                  manifest=str(Path(man["path"]).resolve()), manifest_sha256=man["sha256"], run=man["run"],
                  files=self.files(), jobs=jobs, extra=man["extra"], max_order=self.max_order, new_run=self.new_run,
                  addresses=list(self.site.addresses), seconds_kind=self.site.seconds_kind,
                  rules_file=self.rules_file.value)
        return Opened(rec, [], site_scan, self.rules_file.path, lambda: self.say(f"Record: {path}"))

    def _check(self, site_scan: SiteScan) -> None:
        found = site_scan.blockers()
        if found:
            raise Refused("a record of this site has an order that is open or lost: " + "; ".join(found) +
                          ". Collect an open order with --resume FILE; record what became of a lost one with "
                          "`qdevices resolve`")
        earlier = [s.path for s in site_scan.scans
                   if not s.older and s.path.parent == self.run_dir and s.ledger.any_sent]
        if earlier and not self.new_run:
            raise Refused(f"{earlier[-1]} is an earlier record of this run with jobs that were sent. Go on with "
                          f"--resume {quoted(earlier[-1])}. A new record sends the first orders again: that needs "
                          "--new-run, and it is your decision")
