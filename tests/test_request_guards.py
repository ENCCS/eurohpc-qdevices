"""At each job request of each real site class: every line written is synced, and a request with no answer goes once.

Also the cut of an answer at exactly BODY_LIMIT characters.
"""

import os

import httpx
import pytest
from fakes import QASM, TOKEN, eqe, lines_of, records_of, send, vlq, write_manifest
from fakes.piastq import Broker, piastq_manifest

from qdevices import record
from qdevices.sites import piastq
from qdevices.sites.vlq import VLQ

VLQ_JOB_PATHS = ("/JobManagement/CreateJob", "/FileTransfer/UploadFilesToJobExecutionDir", "/JobManagement/SubmitJob")
VLQ_JOB_REQUESTS = 10     # of one order: the init job's three, then CreateJob, five uploads and SubmitJob


def _eqe_job(request: httpx.Request) -> bool:
    return request.method == "POST" and request.url.path.endswith("/v1/job")


def _piastq_job(request: httpx.Request) -> bool:
    return request.method == "POST" and request.url.path.endswith("/tasks")


def _vlq_job(request: httpx.Request) -> bool:
    return request.url.path.endswith(VLQ_JOB_PATHS)


class Wire:
    """A handler around a fake: each request in order, a check at each job request, and one ConnectError if asked."""

    def __init__(self, fake, is_job, at_job=lambda: None, fail_at: int | None = None) -> None:
        self.fake, self.is_job, self.at_job, self.fail_at = fake, is_job, at_job, fail_at
        self.requests: list[httpx.Request] = []
        self.jobs = 0

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.is_job(request):
            self.at_job()
            self.jobs += 1
            if self.jobs - 1 == self.fail_at:
                raise httpx.ConnectError("no answer", request=request)
        return self.fake(request)


def live(site: str, tmp_path, places, clock, **wire) -> tuple[int, Wire]:
    """One order sent to the fake of a real site class through a Wire: the exit code and the Wire."""
    if site == "euroqexa":
        handler = Wire(eqe.Portal(5, [(0, 1)], []), _eqe_job, **wire)
        made, m = eqe.site(handler), eqe.manifest(tmp_path / "m", QASM)
    elif site == "piastq":
        handler = Wire(Broker(), _piastq_job, **wire)
        made, m = piastq.PiastQ(TOKEN, "M1", transport=httpx.MockTransport(handler)), piastq_manifest(tmp_path / "m")
    else:
        handler = Wire(vlq.FakeVLQ(places), _vlq_job, **wire)
        m = write_manifest(tmp_path / "m", site="vlq", jobs=(("V1", 10),), text=vlq.VLQ_TEXT)
        made = VLQ(vlq.TOKEN, "VLQ", lexis_project="TEST-LEXIS", resource="R1", clock=clock, sleep=clock.sleep,
                   wait_seconds=60, transport=httpx.MockTransport(handler))
    return send(m, made, places, clock, max_order=1), handler


class Syncs:
    """The size of each file at its last fsync from the record module, and the record files with unsynced bytes."""

    def __init__(self, monkeypatch, places) -> None:
        self.places, self.synced, self.unsynced = places, {}, []
        real = os.fsync

        def fsync(fd: int) -> None:
            real(fd)
            found = os.fstat(fd)
            self.synced[found.st_ino] = found.st_size

        monkeypatch.setattr(record.os, "fsync", fsync)

    def check(self) -> None:
        """At a job request: note each record file whose bytes on disk are not all synced."""
        for path in sorted(self.places.records.rglob("*.jsonl")):
            found = path.stat()
            if self.synced.get(found.st_ino) != found.st_size:
                self.unsynced.append((path.name, lines_of(path)[-1]["event"]))


@pytest.mark.parametrize(("site", "jobs"), [("euroqexa", 1), ("piastq", 1), ("vlq", VLQ_JOB_REQUESTS)])
def test_every_line_written_is_synced_before_each_job_request(tmp_path, places, clock, monkeypatch, site, jobs):
    syncs = Syncs(monkeypatch, places)
    code, wire = live(site, tmp_path, places, clock, at_job=syncs.check)
    assert (code, wire.jobs, syncs.unsynced) == (0, jobs, [])


# (site, the job request with no answer, exit): at the init job of VLQ nothing metered was made, so exit 1
NO_ANSWER = [("euroqexa", 0, 2), ("piastq", 0, 2), *(("vlq", n, 1 if n < 3 else 2) for n in range(VLQ_JOB_REQUESTS))]


@pytest.mark.parametrize(("site", "fail_at", "exit_code"), NO_ANSWER)
def test_a_job_request_with_no_answer_is_sent_once_and_no_job_request_follows(tmp_path, places, clock, site,
                                                                              fail_at, exit_code):
    code, wire = live(site, tmp_path, places, clock, fail_at=fail_at)
    failed = [n for n, request in enumerate(wire.requests) if wire.is_job(request)][fail_at]
    later = [request for request in wire.requests[failed + 1:] if wire.is_job(request)]
    assert (code, wire.jobs, later) == (exit_code, fail_at + 1, [])
    stop = lines_of(records_of(places)[0])[-1]
    assert stop["event"] == "stop" and "ConnectError" in stop["error"]


class FailedPortal(eqe.Portal):
    """The portal of a job that ends FAILED, with a cancel reason of `size` characters."""

    def __init__(self, size: int) -> None:
        super().__init__(5, [(0, 1)], [], states=("FAILED",))
        self.reason = "".join(chr(ord("a") + n % 26) for n in range(size))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/cancel_reason"):
            return httpx.Response(200, text=self.reason)
        return super().__call__(request)


@pytest.mark.parametrize("size", [1999, 2000, 2001, 3000])
def test_a_failed_job_keeps_exactly_the_first_2000_characters_of_its_reason(tmp_path, places, clock, size):
    portal = FailedPortal(size)
    _code, lines = eqe.send(eqe.manifest(tmp_path / "m", QASM), portal, places, clock, max_order=1)
    failed = next(line for line in lines if line["event"] == "failed")
    assert failed["logs"]["cancel_reason"] == portal.reason[:2000]
    assert len(failed["logs"]["cancel_reason"]) == min(size, 2000)
