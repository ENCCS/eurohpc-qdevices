"""The send of one job with its lines."""

from .. import manifest as manifests
from ..redact import redact
from ..rules import Point
from ..screen import warn
from ..sites.base import SiteError
from ..sites.protocol import INIT, INIT_JOB, JOB, TABLE_NOTE
from . import hooks
from .call import Call
from .collect import Collect
from .stop import StopKind, UnderWay


class JobSend:
    """One job from its file text to its final line, with a line on disk before each request."""

    def __init__(self, call: Call, job: dict) -> None:
        self.call, self.job = call, job
        self.where = {"order": job["order"], "name": job["name"]}

    def run(self) -> None:
        """The file text, the rules of the job, the work before it, the job request, then the wait."""
        call, where = self.call, self.where
        if self._skipped():         # by a rule before the call
            return
        try:
            self.job = {**self.job, "text": manifests.file_bytes(call.man, self.job)}
        except (manifests.ManifestError, OSError) as exc:
            call.stop(StopKind.CHECK, str(exc), **where)
        job = self.job
        hooks.at(call, Point.BEFORE_JOB, job=job)
        if self._skipped():
            return
        call.under_way = UnderWay(**where, phase="prepare")
        prepared = self._prepare()
        call.under_way = UnderWay(**where, phase="submit")
        # On disk before the request: if no answer is seen, a resume finds it and never sends the order again.
        call.rec.write("submitting", **where, sha256=job["sha256"], shots=job["shots"], options=job["options"])
        call.sent.add(where["order"])
        t0 = call.clock.monotonic()
        try:
            job_id = call.site.submit(job, self.note, prepared)
        except SiteError as exc:
            self._failed(exc)
            return
        self._submitted(job_id, t0)

    def _skipped(self) -> bool:
        if self.where["order"] not in self.call.skipped:
            return False
        self.call.say(f"  order {self.where['order']} ({self.where['name']}): skipped by a rule, not sent")
        return True

    def _prepare(self) -> object:
        call, where = self.call, self.where
        try:
            return call.site.prepare(self.job, self.note)
        except SiteError as exc:
            call.stop(StopKind.PREPARE, f"order {where['order']} ({where['name']}): the work before the job failed: "
                      f"{call.error(exc)['error']}. No metered job was made", **where, **call.error(exc))

    def note(self, step: str, **ids: object) -> None:
        """The `note` a site calls after each request that can make a job exist: one synced line each."""
        call, where = self.call, self.where
        init = step.startswith(INIT)
        held = ids.get(INIT_JOB if init else JOB)
        if held is not None:
            call.under_way.held[INIT_JOB if init else "id"] = held      # before its line: a stop names it
        try:
            call.rec.write("init" if init else "step", **where, step=step, **ids)     # a literal, for the event scan
        except OSError as exc:
            if held is not None:
                warn(redact(f"RECORD WRITE FAILED ({type(exc).__name__}): order {where['order']} ({where['name']}), "
                            f"{'init job' if init else 'job'} {held}: its {step} line may not be in the record; "
                            "write this id down", call.secrets()))
            raise
        if init and ids.get(TABLE_NOTE):
            call.say(f"  NOTE: order {where['order']} ({where['name']}): {ids[TABLE_NOTE]}")

    def _failed(self, exc: SiteError) -> None:
        """A job request with no good answer: a refusal is final, anything else leaves the order unknown."""
        call, job, where = self.call, self.job, self.where
        info, known = call.error(exc), call.under_way.held.get("id")
        if call.site.classify(exc) == "refused":
            call.final("refused", f"  refused by the site: {info['error']}", **where, id=known, **info)
            hooks.at(call, Point.ON_REFUSAL, {"kind": "refused", "id": known, "reason": info["error"],
                                              "http_status": exc.status, "body": info["body"]}, job=job)
            return
        what = f"job {known} was made; a resume reads its state" if known is not None else \
            "a resume stops at it until you record what became of it with `qdevices resolve`"
        call.stop(StopKind.UNKNOWN, f"order {job['order']} ({job['name']}): {info['error']} at {exc.step}. It is not "
                  f"known if a job runs. The order is never sent again: {what}", **where, id=known, **info,
                  **({"id_no_url": True} if exc.no_url else {}))

    def _submitted(self, job_id: object, t0: float) -> None:
        call = self.call
        line = dict(self.where, id=job_id, submitted_utc=call.clock.utc().isoformat())
        call.unwritten = line         # an interrupt before the write still stores the id
        call.under_way.held["id"] = job_id
        call.say(f"  job {job_id} sent")
        call.rec.write("submitted", **line)
        call.unwritten = None
        call.site.sent_at(job_id, line["submitted_utc"])
        Collect(call, self.job, job_id, True, t0).run()
