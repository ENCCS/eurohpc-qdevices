"""A fake MQSS portal (httpx.MockTransport) for the Euro-Q-Exa class, and the helpers of its tests."""

import json

import httpx

from qdevices import runner
from qdevices.sites import euroqexa

from .core import TOKEN, cfg, lines_of, records_of, turn, write_manifest
from .service import Service

# Local stamps: UTC+1 in January, one hour ahead of the fake clock.
STAMPS = {"timestamp_submitted": "2026-01-05 13:00:00", "timestamp_scheduled": "2026-01-05 13:00:01",
          "timestamp_completed": "2026-01-05 13:00:03"}


class Portal(Service):
    """Machine M1 with these qubits and cz loci, in the forms the portal gives; each job ends with these stamps."""

    ROUTES = (("/resources/M1", "_machine"), ("num_pending_jobs", {"num_pending_jobs": 0}),
              ("/v1/job", {"uuid": "u-1"}), ("/status", "_status"), ("/result", "_result"))

    def __init__(self, qubits: int, pairs, seen: list, *, stamps=STAMPS, states=("COMPLETED",)) -> None:
        self.qubits, self.seen, self.stamps, self.states = qubits, seen, stamps, list(states)
        self.loci = ", ".join(f"({a}, {b}): None" for a, b in pairs)

    def keep(self, request):
        self.seen.append((request.method, request.url.path))

    def _machine(self, request):
        return httpx.Response(200, json={"name": "M1", "qubits": self.qubits, "online": True,
                                         "instructions": f"[('r', {{}}), ('cz', {{{self.loci}}})]"})

    def _status(self, request):
        return httpx.Response(200, json={"status": turn(self.states)})

    def _result(self, request):
        return httpx.Response(200, json={"result": json.dumps({"1": 10}), **self.stamps})


def site(handler) -> euroqexa.EuroQExa:
    return euroqexa.EuroQExa(TOKEN, "M1", transport=httpx.MockTransport(handler))


def manifest(folder, text: bytes, *, no_modify: bool = False, **extra):
    """A manifest of one job, J1 with 10 shots, for machine M1; `extra` keys go to its head."""
    path = write_manifest(folder, jobs=(("J1", 10),), text=text, **extra)
    if no_modify:
        data = json.loads(path.read_text())
        data["jobs"][0]["options"] = {"no_modify": True}
        path.write_text(json.dumps(data))
    return path


def send(path, handler, places, clock, conf=None, **kw) -> tuple[int, list[dict]]:
    """One live call over the fake portal: the exit code and the lines of the record."""
    code = runner.send(path, site(handler), cfg=conf or cfg(), places=places, clock=clock, sleep=clock.sleep,
                       host="h", say=lambda *a, **k: None, **kw)
    return code, lines_of(records_of(places)[0])


def posts(seen: list) -> list:
    return [s for s in seen if s[0] == "POST"]
