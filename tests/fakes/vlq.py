"""A fake HEAppE, LEXIS and status file (httpx.MockTransport) for the VLQ class, and the helpers of its tests.

A results file holds only classes of tests/vlq_fake.py and a uuid.UUID: neutral module names.
"""

import base64
import json
import pickle
import uuid

import httpx
from vlq_fake import Counts, Experiment, JobRecord, Parameters, Results

from qdevices import runner
from qdevices.sites.vlq import VLQ

from .core import FakeClock, cfg, lines_of, places_in, records_of, turn, write_manifest
from .service import Service

PASSWORDS_SEEN = []
VLQ_TEXT = (b'OPENQASM 3.0;\ninclude "stdgates.inc";\ngate r(theta, phi) q {\n    gphase(0);\n}\n'
            b"qubit[1] q;\nbit[1] c;\nr(pi, 0) q[0];\nc[0] = measure q[0];\n")
_CLAIMS = base64.urlsafe_b64encode(json.dumps({"exp": 1767614400 + 7200}).encode()).decode().rstrip("=")
TOKEN = "eyJ" + "h" * 20 + "." + _CLAIMS + ".sig"
CALIBRATION = "5f0c1a2b-3c4d-4e5f-8a9b-0c1d2e3f4a5b"      # synthetic
STATUS_PATH = "/vlq-status.json"
STATUS_UP = {"QPU_status": True, "QCCW_status": True, "queue_available": True, "total_status": True,
             "timestamp": "2026-01-05T11:59:00+00:00"}

__all__ = ["CALIBRATION", "PASSWORDS_SEEN", "STATUS_UP", "TOKEN", "VLQ_TEXT", "Counts", "Experiment", "FakeVLQ",
           "Parameters", "Results", "creates", "go", "make_vlq", "results_file", "submits"]


def results_file(counts=None) -> bytes:
    """A results.pkl with the counts and, in the parameters of the result, CALIBRATION as a uuid.UUID."""
    ident = uuid.UUID(CALIBRATION, is_safe=uuid.SafeUUID.safe)     # its state holds int and is_safe
    return pickle.dumps(Results(Experiment(Counts(counts or {"1": 10}), Parameters(ident))))


def _node(i, name, tid, tname):
    templates = [{"Name": tname, "Id": tid, "IsEnabled": True}]
    return {"Id": i, "Name": name, "MaxWalltime": 7200, "FileTransferMethodId": 1,
            "Accounting": [{"Formula": "NumNodes * RunTime"}],
            "Projects": [{"AccountingString": "R1", "CommandTemplates": templates}]}


_RESOURCES = [{"Name": "R1", "Assignments": [{"ProjectResourceId": "res-1", "LocationName": "loc"}]}]
_CLUSTERS = [{"Id": 1, "Name": "C", "NodeTypes": [_node(2, "init_queue", 10, "RunQInit"),
                                                 _node(3, "compute_queue", 11, "RunQExecute")]}]


class FakeVLQ(Service):
    """Scripted HEAppE, LEXIS and status file; `states` maps a job id to the states it reports, in turn."""

    ROUTES = (("/Project", [{"ShortName": "TEST-LEXIS"}]),
              ("/ProjectResource", _RESOURCES),
              ("ProjectsForCurrentUser", [{"Project": {"Id": 3, "Name": "P", "AccountingString": "R1"}}]),
              ("ListAvailableClusters", _CLUSTERS), ("DryRunJob", {"JobId": None}), ("CreateJob", "_create"),
              ("UploadFilesToJobExecutionDir", "_upload"), ("SubmitJob", "_submit"),
              ("CurrentInfoForJob", "_info"), ("DownloadFileFromCluster", "_download"))

    def __init__(self, places, *, states=None, fail=None, status_file=None):
        self.places, self.states = places, dict(states or {})
        self.fail = dict(fail or {})      # ("upload" or "submit", job id) -> the HTTP code of one answer
        self.requests, self.next_id, self.last_line_at = [], 100, {}
        self.status_file = dict(STATUS_UP) if status_file is None else status_file
        self.results_pkl, self.headers = results_file(), []

    def last(self):
        found = records_of(self.places)
        return lines_of(found[-1])[-1] if found else None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == STATUS_PATH:       # the whole path, not its end
            self.keep(request)
            return self._status_file(request)
        return super().__call__(request)

    def keep(self, request):
        path = request.url.path
        self.requests.append((request.method, path, dict(request.url.params)))
        self.headers.append((path, {name.lower(): value for name, value in request.headers.items()}))

    def _failed(self, key) -> httpx.Response | None:
        return httpx.Response(self.fail.pop(key), text="no") if key in self.fail else None

    def _status_file(self, request):
        if isinstance(self.status_file, Exception):
            raise self.status_file
        if isinstance(self.status_file, int):
            return httpx.Response(self.status_file, text="no")
        if isinstance(self.status_file, bytes):
            return httpx.Response(200, content=self.status_file)
        return httpx.Response(200, json=self.status_file)

    def _create(self, request):
        body = json.loads(request.content)
        env = {e["Name"]: e["Value"] for e in body["JobSpecification"]["EnvironmentVariables"]}
        PASSWORDS_SEEN.append(env["USER_JWT_PWD"])
        self.next_id += 1
        self.last_line_at[("create", env["Q_COMMAND"])] = self.last()
        return httpx.Response(200, json={"Id": self.next_id, "Tasks": [{"Id": self.next_id * 10}], "State": 1})

    def _upload(self, request):
        job = int(request.url.params["JobId"])
        failed = self._failed(("upload", job))
        if failed is not None:
            return failed
        name = request.content.split(b'filename="')[1].split(b'"')[0].decode()
        self.last_line_at.setdefault(("upload", job), self.last())
        return httpx.Response(200, json=[{"FileName": name, "Succeeded": True}])

    def _submit(self, request):
        job = json.loads(request.content)["CreatedJobInfoId"]
        failed = self._failed(("submit", job))
        if failed is not None:
            return failed
        self.last_line_at[("submit", job)] = self.last()
        return httpx.Response(200, json={"Id": job, "Tasks": [{"Id": job * 10}], "State": 2})

    def _info(self, request):
        job = int(request.url.params["SubmittedJobInfoId"])
        state = turn(self.states.get(job, [16]))
        if state is None:
            return httpx.Response(500, text="")
        return httpx.Response(200, json={"Id": job, "State": state, "Tasks": [{"Id": job * 10}],
                                         "StartTime": "2026-01-05T12:00:00", "EndTime": "2026-01-05T12:00:20"})

    def _download(self, request):
        name = json.loads(request.content)["RelativeFilePath"].rsplit("/", 1)[-1]
        data = {"results.pkl": self.results_pkl, "job.pkl": pickle.dumps(JobRecord(0.42))}
        return httpx.Response(200, json=base64.b64encode(data.get(name, b"artefact")).decode())


def make_vlq(tmp_path, **kw):
    """(places, clock, fake service, manifest of two jobs, VLQ site over the fake service)."""
    places, clock = places_in(tmp_path), FakeClock()
    fake = FakeVLQ(places, **kw)
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("V1", 10), ("V2", 10)), text=VLQ_TEXT)
    site = VLQ(TOKEN, "VLQ", lexis_project="TEST-LEXIS", resource="R1", clock=clock, sleep=clock.sleep,
               wait_seconds=60, transport=httpx.MockTransport(fake))
    return places, clock, fake, m, site


def go(m, site, places, clock, say=lambda *a, **k: None, **kw):
    return runner.send(m, site, cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="h", say=say, **kw)


def creates(fake):
    return [r for r in fake.requests if r[1].endswith("CreateJob")]


def submits(fake):
    return [r for r in fake.requests if r[1].endswith("SubmitJob")]
