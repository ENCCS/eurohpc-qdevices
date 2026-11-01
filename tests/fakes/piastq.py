"""A fake PCSS broker (httpx.MockTransport) for the Piast-Q class, and the helpers of its tests."""

import json

import httpx

from qdevices.sites import piastq

from .core import TOKEN, send, turn, write_manifest
from .service import Service, answer

PAYLOAD = json.dumps({"number_of_qubits": 2, "quantum_circuit": [
    {"operation": "RXX", "qubits": [0, 1], "theta": 0.5}, {"operation": "MEASURE"}]}).encode()
BUSY = json.dumps({"detail": json.dumps({"quantum_api_status_code": 429, "message": "max connections reached: 4"})})
COUNTS = {"result": [[0, 0]] * 6 + [[1, 1]] * 4}
EXPIRED = {"status": "error", "code": 4, "message": "Unknown job. May be expired."}


class Broker(Service):
    """The broker: `results` and `states` are the answers in turn, and the last one stays."""

    ROUTES = (("/machines", {"names": ["M1"]}), ("/tasks", {"uid": "p-1"}), ("/status", "_status"),
              ("/results", "_results"))

    def __init__(self, results=(), states=()):
        self.results = list(results) or [answer(200, json=COUNTS)]
        self.states = list(states) or [answer(200, json={"status": "Completed"})]
        self.requests = []

    def keep(self, request):
        self.requests.append((request.method, request.url.path))

    def _status(self, request):
        return turn(self.states)()

    def _results(self, request):
        return turn(self.results)()

    def count(self, method, end):
        return len([r for r in self.requests if r[0] == method and r[1].endswith(end)])

    def site(self):
        return piastq.PiastQ(TOKEN, "M1", transport=httpx.MockTransport(self))


def piastq_manifest(folder):
    return write_manifest(folder, site="piastq", jobs=(("J1", 10),), text=PAYLOAD)


def run_broker(tmp_path, places, clock, broker, **kw):
    """A send of one Piast-Q job to the fake broker: a new record, or with resume=RECORD a collect."""
    kw = kw or {"max_order": 1}
    return send(piastq_manifest(tmp_path / "m"), broker.site(), places, clock, **kw)
