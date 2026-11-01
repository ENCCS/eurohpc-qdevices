"""From a job id to a final line. Never submits and never cancels."""

from datetime import datetime
from typing import NoReturn

from .. import billing
from ..resolve import EXPIRED_MINUTES
from ..rules import Point
from ..sites.base import Expired, SiteError
from . import hooks
from .call import Call
from .stop import StopKind, UnderWay


class Collect:
    """The wait for one job, then its final line: a result, a failed state, or "not submitted"."""

    def __init__(self, call: Call, job: dict, job_id: object, submitted: bool, t0: float | None) -> None:
        self.call, self.job, self.job_id, self.submitted, self.t0 = call, job, job_id, submitted, t0
        self.where = {"order": job["order"], "name": job["name"], "id": job_id}
        self.last, self.polls = None, 0
        self.failure, self.misses, self.deadline = None, 0, 0.0

    @property
    def label(self) -> str:
        """The order and its job, as a stop names them."""
        return f"order {self.job['order']} ({self.job['name']}), job {self.job_id}"

    @property
    def note(self) -> str:
        """The word of the site on when to collect an open order, for a stop that leaves it open."""
        note = self.call.site.collect_note
        return f". {note}" if note else ""

    def run(self) -> None:
        """The polls of the job, to its final line or a stop."""
        call = self.call
        call.under_way = UnderWay(order=self.job["order"], name=self.job["name"], held={"id": self.job_id})
        wait_seconds = float(call.site_config["wait_seconds"])
        self.deadline = call.clock.monotonic() + wait_seconds
        while not self._poll():
            if call.clock.monotonic() >= self.deadline:
                call.stop(StopKind.TIMEOUT, f"{self.label}: still {self.last} after {wait_seconds:.0f} s. Not "
                          f"cancelled: the job stays open and a resume collects it{self.note}", **self.where,
                          state=self.last)
            call.sleep(call.site.poll_seconds)

    def _poll(self) -> bool:
        """One read of the state: True when the order has its final line."""
        try:
            state = self.call.site.status(self.job_id)
        except SiteError as exc:
            self._missed(exc, "the state cannot be read", StopKind.STATUS_ERROR, "a resume collects it")
            return False
        if state is None:           # no state: a missed poll with no line
            return False
        self._seen(state)
        if state.get("configuring") and not self.submitted:
            self._configuring(state)
            return True
        if state["final"]:
            if state["ok"]:
                self._result()
            else:
                self._failed(state)
            return True
        return False

    def _seen(self, state: dict) -> None:
        """Count a poll, and write a "status" line when the state has changed."""
        self.polls += 1
        self.failure = None
        if state["state"] != self.last:
            self.call.rec.write("status", **self.where, state=state["state"], poll=self.polls)
            self.last = state["state"]

    def _missed(self, exc: SiteError, what: str, kind: StopKind, then: str) -> None:
        """A read that failed: a stop that leaves the order open, or a missed poll, asked again at the next poll."""
        call = self.call
        if isinstance(exc, Expired):
            self._expired(exc)
        missed = exc.missed
        if missed is None or call.clock.monotonic() >= self.deadline:
            info = call.error(exc)
            missed_before = f", after {self.misses} missed polls" if self.misses else ""
            call.stop(kind, f"{self.label}: {what}: {info['error']}{missed_before}. The order stays open; {then}"
                      f"{self.note}", **self.where, **info, missed_polls=self.misses)
        self.misses += 1
        if (exc.step, missed) != self.failure:       # a "status" line when the kind of failure changes
            call.rec.write("status", **self.where, missed=missed, misses=self.misses, **call.error(exc))
            self.failure = (exc.step, missed)

    def _configuring(self, state: dict) -> None:
        """A job made and never seen as submitted, that the site shows as still being configured."""
        call, order = self.call, self.job["order"]
        if not call.submit_never_sent(order, self.job_id):
            call.stop(StopKind.SUBMIT_UNKNOWN, f"{self.label}: the site shows it {state['state']} and the record has "
                      "no 'submitted' line, but the submit request may have reached the site. The job is not "
                      "cancelled and is never sent again; the order stays open. Check the job at the site: when it "
                      f"has left {state['state']}, a resume collects it; when the site shows that it never ran, "
                      f"record it with: {call.resolve_command(order, '--none')}", **self.where, state=state["state"])
        reason = "it was created and never submitted, so it used no device time"
        call.final("not_submitted", f"  job {self.job_id}: not submitted, final", **self.where, state=state["state"],
                   reason=reason)
        hooks.at(call, Point.ON_REFUSAL, {"kind": "not_submitted", "id": self.job_id, "reason": reason}, job=self.job)

    def _failed(self, state: dict) -> None:
        call = self.call
        try:
            logs = call.site.logs(self.job_id)
        except SiteError:
            logs = {}
        call.final("failed", f"  job {self.job_id}: ended {state['state']}", **self.where, state=state["state"],
                   logs=logs)
        hooks.at(call, Point.ON_REFUSAL, {"kind": "failed", "id": self.job_id, "state": state["state"],
                                          "reason": f"the job ended {state['state']}"}, job=self.job)

    def _expired(self, exc: Expired) -> NoReturn:
        """The site answered that it does not know the job: the order stays open until `resolve --expired`."""
        call = self.call
        call.stop(StopKind.RESULT_EXPIRED, f"{self.label}: the site does not know the job any more, so its result may "
                  f"be lost ({call.error(exc)['error']}). The order stays open and is never sent again. Resume once "
                  f"more, {EXPIRED_MINUTES} minutes or more later; when two calls got this answer, record it "
                  f"with: {call.resolve_command(self.job['order'], '--expired')}", **self.where, **call.error(exc))

    def _result(self) -> None:
        call, job = self.call, self.job
        while True:
            try:
                result = call.site.result(self.job_id)
                break
            except SiteError as exc:
                self._missed(exc, "the result cannot be read", StopKind.RESULT_ERROR, "a resume reads it again")
            call.sleep(call.site.poll_seconds)
        wall = None if self.t0 is None else round(call.clock.monotonic() - self.t0, 3)
        seconds = self._seconds(result.get("seconds"), wall)
        line = {**self.where, "shots": job["shots"], **{k: v for k, v in result.items() if k != "seconds"},
                "seconds": seconds, "seconds_kind": call.site.seconds_kind, "wall_seconds": wall,
                "published_seconds": billing.published_seconds(call.site.name, job["shots"]), "polls": self.polls,
                "recovered": self.t0 is None}
        call.rec.write("result", **line)         # on disk before its text is made, which can raise
        call.results[job["order"]] = line
        call.under_way = UnderWay()
        call.say(f"  job {self.job_id}: result in the record" + ("" if seconds is None else f", {seconds:.3f} s"))
        hooks.at(call, Point.AFTER_RESULT, line, job=job)

    def _seconds(self, seconds: float | None, wall: float | None) -> float | None:
        """The seconds the site gave; at a site that gives none and counts wall time, the wall seconds."""
        call = self.call
        if seconds is not None or call.site.seconds_kind != "wall":
            return seconds
        if wall is not None:
            return wall
        since = call.submitted_utc(self.job["order"])
        if since:
            return round((call.clock.utc() - datetime.fromisoformat(since)).total_seconds(), 3)
        return seconds
