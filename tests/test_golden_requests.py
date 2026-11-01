"""Each request to each site, in order: its method, URL, headers and body, through a wrapper around the fakes.

At each request that can make a job exist, the last line on disk is pinned: it is synced before the request goes.
The bytes are those of the httpx of pixi.lock.
"""

import hashlib
import json

import httpx
from fakes import QASM, TOKEN, eqe, lines_of, records_of, send, vlq, write_manifest
from fakes.piastq import Broker

from qdevices.sites import piastq
from qdevices.sites.vlq import VLQ

OWN = ("host", "accept", "accept-encoding", "connection", "user-agent")    # httpx sets these on every request
SEALED = b'filename="user_token.enc"'      # the sealed token upload: a new envelope at each job
VLQ_JOB_PATHS = ("/JobManagement/CreateJob", "/FileTransfer/UploadFilesToJobExecutionDir", "/JobManagement/SubmitJob")
# A Piast-Q file with quantum_circuit first: the task request keeps that order.
FLIPPED = json.dumps({"quantum_circuit": [{"operation": "RXX", "qubits": [0, 1], "theta": 0.5},
                                          {"operation": "MEASURE"}], "number_of_qubits": 2}).encode()


def on_disk(places) -> str:
    """The event, and the step if it has one, of the last line on disk of the record; "none" with no record."""
    found = records_of(places)
    last = lines_of(found[-1])[-1] if found else {}
    return " ".join(str(last[key]) for key in ("event", "step") if key in last) or "none"


class Wire:
    """A handler around a fake: it writes down each request, and at a job request the last line on disk."""

    def __init__(self, fake, places, job_request) -> None:
        self.fake, self.places, self.job_request = fake, places, job_request
        self.lines: list[str] = []
        self.at_jobs: list[str] = []
        self.masks: dict[str, str] = {}
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.lines.append(f"{request.method} {request.url}")
        self.lines += [f"  {name}: {value}" for name, value in request.headers.items() if name not in OWN]
        self.lines += self.body(request)
        if self.job_request(request):
            self.at_jobs.append(on_disk(self.places))
            self.lines.append(f"  last line on disk: {self.at_jobs[-1]}")
        return self.fake(request)

    def body(self, request: httpx.Request) -> list[str]:
        """The body as text, or for a file upload the head, the size and the SHA-256 of each part."""
        kind = request.headers.get("content-type", "")
        if not kind.startswith("multipart/form-data"):
            return [f"  body: {request.content.decode('utf-8')}"] if request.content else []
        boundary = kind.split("boundary=", 1)[1]
        self.masks[boundary] = "<BOUNDARY>"
        out = []
        for chunk in request.content.split(b"--" + boundary.encode())[1:-1]:
            head, _, content = chunk[2:-2].partition(b"\r\n\r\n")     # each part starts and ends with CRLF
            digest = hashlib.sha256(content).hexdigest()
            if SEALED in head:
                self.masks[digest] = "<SEALED>"
            headers = head.decode("utf-8").replace("\r\n", " | ")
            out += [f"  part: {headers}", f"    {len(content)} bytes, sha256 {digest}"]
        return out

    def text(self) -> str:
        return "\n".join(self.lines) + "\n"


def test_euroqexa_one_job_with_the_bytes_of_its_job_request(tmp_path, places, clock, golden):
    wire = Wire(eqe.Portal(5, [(0, 1)], []), places,
                lambda request: request.method == "POST" and request.url.path.endswith("/v1/job"))
    assert send(eqe.manifest(tmp_path / "m", QASM), eqe.site(wire), places, clock, max_order=1) == 0
    assert wire.at_jobs == ["submitting"]
    golden("requests_euroqexa_one_job", wire.text(), masks={TOKEN: "<TOKEN>", **wire.masks})


def test_piastq_one_job_keeps_the_key_order_of_its_file(tmp_path, places, clock, golden):
    wire = Wire(Broker(), places, lambda request: request.method == "POST" and request.url.path.endswith("/tasks"))
    m = write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 10),), text=FLIPPED)
    assert send(m, piastq.PiastQ(TOKEN, "M1", transport=httpx.MockTransport(wire)), places, clock, max_order=1) == 0
    assert wire.at_jobs == ["submitting"]
    task = next(request for request in wire.requests if request.method == "POST")
    assert list(json.loads(task.content)["payload"]) == ["repetitions", "quantum_circuit", "number_of_qubits"]
    golden("requests_piastq_one_job", wire.text(), masks={TOKEN: "<TOKEN>", **wire.masks})


def test_vlq_two_orders_with_their_init_jobs_uploads_and_downloads(tmp_path, places, clock, golden):
    wire = Wire(vlq.FakeVLQ(places), places, lambda request: request.url.path.endswith(VLQ_JOB_PATHS))
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("V1", 10), ("V2", 10)), text=vlq.VLQ_TEXT)
    site = VLQ(vlq.TOKEN, "VLQ", lexis_project="TEST-LEXIS", resource="R1", clock=clock, sleep=clock.sleep,
               wait_seconds=60, transport=httpx.MockTransport(wire))
    assert send(m, site, places, clock, max_order=2) == 0
    status = [request for request in wire.requests if request.url.path == "/vlq-status.json"]
    assert len(status) == 1 and "authorization" not in status[0].headers
    # The token, then each envelope password raw and in base64 (a job's USER_JWT_PWD).
    masks = {vlq.TOKEN: "<TOKEN>", **dict.fromkeys(site.secrets()[1:], "<USER_JWT_PWD>"), **wire.masks}
    golden("requests_vlq_two_orders", wire.text(), masks=masks)
