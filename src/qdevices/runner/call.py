"""`Call`: the state of one live call, and the lines it writes."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, NoReturn, Self

from .. import record as records
from ..ledger import Ledger, Outcome, Status, job_id
from ..redact import redact
from ..screen import quoted
from ..sites.base import SiteError
from ..sites.protocol import SiteProtocol
from .stop import StopKind, Stopped, UnderWay

if TYPE_CHECKING:
    from .opening import Opened


@dataclass
class Call:
    """One live call: the manifest, the site, its record, and what the call has done so far."""

    man: dict
    site: SiteProtocol
    site_config: dict
    rec: records.Record
    prior: list[dict]
    clock: object
    sleep: object
    say: object
    user: dict
    used_other: float = 0.0
    results: dict = field(default_factory=dict)       # order -> result line
    sent: set = field(default_factory=set)            # orders with a "submitting" line in this call
    skipped: set = field(default_factory=set)         # orders a rule said not to send
    under_way: UnderWay = field(default_factory=UnderWay)
    unwritten: dict | None = None                     # a "submitted" line not yet on disk
    rules_path: str | None = None                     # the rules file the record is held to, for printed commands

    @classmethod
    def from_opening(cls, man: dict, site: SiteProtocol, site_config: dict, opened: "Opened", *, clock: object,
                     sleep: object, say: object, user: dict) -> Self:
        """The call on an opened record, with the seconds the other records of the site used."""
        call = cls(man, site, site_config, opened.rec, opened.prior, clock=clock, sleep=sleep, say=say, user=user,
                   rules_path=opened.rules_path)
        call.used_other = opened.site_scan.used_elsewhere(opened.rec.path.resolve(), man["project"], call.job_limit)
        return call

    def __post_init__(self) -> None:
        shown = self.say
        self.say = lambda text="": shown(redact(text, self.secrets()))       # the token filter on the screen
        prior = Ledger(self.prior)
        self.skipped |= prior.skipped
        for o in prior.orders.values():
            if o.final == Outcome.RESULT:
                self.results[o.order] = o.result

    # ------------------------------------------------------------ what the call knows

    @property
    def job_limit(self) -> float:
        """The job time limit of the site, in seconds."""
        return float(self.site_config["job_seconds_limit"])

    def lines(self) -> list[dict]:
        """The lines of the record: those it held before this call, then those of this call."""
        return self.prior + self.rec.lines

    def secrets(self) -> list[str]:
        """The secrets of the site at this moment, as they grow during a call."""
        return self.site.secrets()

    def used(self) -> float:
        """The seconds used for the budget: in the other records, and in this one."""
        return round(self.used_other + Ledger(self.lines()).used_seconds(self.job_limit), 6)

    def touched(self) -> set:
        """The orders that are no longer unsent: in the record, or sent in this call."""
        return {o for o, s in Ledger(self.lines()).orders.items() if s.status != Status.UNSENT} | self.sent

    def submitted_utc(self, order: int) -> str | None:
        """The time of the last 'submitted' line of an order: its submitted_utc, or else its utc."""
        lines = Ledger(self.lines()).lines_of(order, "submitted")
        return lines[-1].get("submitted_utc") or lines[-1].get("utc") if lines else None

    def submitting_utc(self, order: int) -> str | None:
        """The utc of the last 'submitting' line of an order: written just before its job request."""
        lines = Ledger(self.lines()).lines_of(order, "submitting")
        return lines[-1].get("utc") if lines else None

    def submit_never_sent(self, order: int, job: object) -> bool:
        """True only if the record shows that the submit request of this job was never sent."""
        made_step, submit_step = self.site.made_step, self.site.submit_step
        if made_step is None or submit_step is None:
            return False
        steps = Ledger(self.lines()).lines_of(order, "step")
        made = any(e.get("step") == made_step and job_id(e) == job for e in steps)
        return made and not any(e.get("step") == submit_step for e in steps)

    def resume_command(self, more: str = "") -> str:
        """The command the app prints to go on with this record, with the rules file it is held to."""
        rules = f" --rules {quoted(self.rules_path)}" if self.rules_path else ""
        return f"qdevices send {quoted(self.man['path'])} --live --resume {quoted(self.rec.path)}{more}{rules}"

    def resolve_command(self, order: int, how: str) -> str:
        """The command the app prints to record what became of an order."""
        return f"qdevices resolve {quoted(self.rec.path)} {order} {how}"

    # ------------------------------------------------------------ what the call writes

    def error(self, exc: SiteError) -> dict:
        """The fields of a site error for a line, with every secret taken out."""
        secrets = self.secrets()
        body = redact(exc.body, secrets)[:200] if exc.body else None
        return {"error": redact(str(exc), secrets)[:300], "http_status": exc.status, "body": body,
                "step": exc.step}

    def stop(self, kind: StopKind, reason: str, **fields: object) -> NoReturn:
        """The stop line, what to say of it, then `Stopped`, which ends the call."""
        self.rec.write("stop", reason=reason, kind=kind.value, **fields)
        self.say(f"STOP: {reason}")
        self.say(f"Record: {self.rec.path}")
        raise Stopped(kind)

    def final(self, event: str, said: str, /, **fields: object) -> None:
        """The last line of an order, then nothing under way, then what to say of it."""
        self.rec.write(event, **fields)
        self.under_way = UnderWay()
        self.say(said)

    def write_unwritten(self) -> None:
        """Write a "submitted" line whose first write was cut by an interrupt or an error."""
        if self.unwritten is not None:
            self.rec.write("submitted", **self.unwritten)
            self.unwritten = None
