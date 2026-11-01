"""The init job of a VLQ order: it writes the two artefacts the metered job needs. No device time.

Its lines are on disk before each next request; HEAppE books its node time, which the record keeps.
"""

from dataclasses import dataclass

from ...clock import Clock, Sleep, seconds_between
from ..base import SiteError
from ..protocol import INIT_CREATED, INIT_STATUS, Note
from .heappe import HeappeJobs
from .table import Table
from .target import Target
from .wire import ARTEFACTS, TABLE_FILE, HeappeState, JobKind, digests


@dataclass(frozen=True, slots=True, kw_only=True)
class InitJob:
    """The init job of one order on its target: made, given the token, sent, waited for, and its artefacts read."""

    jobs: HeappeJobs
    target: Target
    clock: Clock
    sleep: Sleep
    wait_seconds: float
    poll_seconds: float
    kind: JobKind

    def run(self, note: Note, text: str) -> dict:
        """{"init_job", "artefacts"}: the artefacts as bytes, for the uploads of the metered job."""
        location = self.target.resource.get("location_name")
        extra = {"Q_OPTIONAL_ARG": location} if location else None
        note("init_submitting")
        job = self.jobs.create(self.target, self.kind, "init_create", extra)
        note(INIT_CREATED, init_job=job.id, task=job.task)
        self.jobs.upload_token(job, "init_upload")
        self.jobs.submit(job.id, "init_submit")
        note("init_submitted", init_job=job.id)
        info = self.wait(job.id)
        state = HeappeState.of(info["State"])
        note(INIT_STATUS, init_job=job.id, state=state.name,
             node_seconds=seconds_between(info.get("StartTime"), info.get("EndTime"), 3))
        if not state.ok:
            raise SiteError(f"init job {job.id} ended {state.name}; no metered job was made", step="init_failed")
        artefacts = {name: self.jobs.download(job.id, name, "init_download") for name in ARTEFACTS}
        fields, problems = Table.review(artefacts[TABLE_FILE], text)
        note("init_done", init_job=job.id, files=digests(artefacts), **fields)
        if problems:
            more = f" (and {len(problems) - 1} more on the init_done line)" if len(problems) > 1 else ""
            raise SiteError(f"the text does not fit the table of the day: {problems[0]}{more}. The order is not "
                            "sent; a resume makes a new init job and checks again", step="table")
        return {"init_job": job.id, "artefacts": artefacts}

    def wait(self, init_id: object) -> dict:
        """The info of the init job once its state ends the wait. It is never cancelled."""
        deadline = self.clock.monotonic() + self.wait_seconds
        while True:
            info = self.jobs.info(init_id, "init_wait")
            state = HeappeState.of(info["State"])
            if state.final:
                return info
            if self.clock.monotonic() >= deadline:
                raise SiteError(f"init job {init_id} still {state.name} after {self.wait_seconds:.0f} s; it is not "
                                "cancelled", step="init_wait")
            self.sleep(self.poll_seconds)
