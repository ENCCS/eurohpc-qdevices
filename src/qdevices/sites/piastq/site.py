"""Piast-Q at PCSS, over HTTP to the PCSS broker.

The broker is that of pcss-qapi 0.2.2 (0.3.0 and 0.3.1 talk to another service); it caps connections, so one is used.
"""

import json
from typing import TYPE_CHECKING, Any, Final

from ..base import Expired, Site, SiteError, cut
from ..facts import SHARED_KEYS, Profile, Rule
from ..protocol import JobState, Note, Refusal
from .broker import EXPIRED_CODE, EXPIRED_MESSAGE, circuit_problems, payload_of, unsendable

if TYPE_CHECKING:
    import httpx

ADDRESS: Final = "https://api.quantum.psnc.pl/api/open"
SITE_MAX_SHOTS: Final = 200           # per job in the maker's client library 1.15.0; site_max_shots replaces it
DONE: Final = frozenset({"completed", "finished"})
FAILED: Final = frozenset({"failed", "error", "cancelled", "canceled"})
LOGIN: Final = ("Piast-Q: the API key that PCSS issues for the broker; no public page says how it is issued.",)
BILLING: Final = Rule("no public rule; the records give wall seconds only")


def _busy(body: str | None) -> bool:
    """True when the answer to a 422 is the upstream 429 of too many connections."""
    try:
        detail = json.loads(body or "").get("detail", "")
        inner = json.loads(detail) if isinstance(detail, str) else detail
        return isinstance(inner, dict) and inner.get("quantum_api_status_code") == 429
    except (ValueError, AttributeError, TypeError, RecursionError):
        return False


def _expired(answer: object) -> bool:
    """True when an answer, a text or its JSON, holds the broker's code 4 and its message of an expired job."""
    try:
        reply = json.loads(answer) if isinstance(answer, str) else answer
    except (ValueError, RecursionError):
        return False
    return isinstance(reply, dict) and reply.get("code") == EXPIRED_CODE and reply.get("message") == EXPIRED_MESSAGE


def _counts(reply: object) -> dict[str, int]:
    """Counts from the per-shot lists. Element i of a shot is qubit i, so qubit 0 is the leftmost bit."""
    shots = reply.get("result") if isinstance(reply, dict) else None
    if not isinstance(shots, list) or not all(isinstance(s, list) for s in shots):
        raise SiteError("the result is not a list of shots", body=cut(reply), step="result")
    counts: dict[str, int] = {}
    for shot in shots:
        try:
            key = "".join(str(int(b)) for b in shot)
        except (ValueError, TypeError, OverflowError):
            raise SiteError("a shot of the result is not a list of bits", body=cut(reply), step="result") from None
        counts[key] = counts.get(key, 0) + 1
    return counts


class PiastQ(Site):
    """Piast-Q at PCSS: one task request makes and runs a job, over one connection to the broker."""

    name = "piastq"
    token_env = "PCSS_API_KEY"
    profile = Profile(title="Piast-Q", operator="PCSS", login=LOGIN, billing=BILLING, config_keys=SHARED_KEYS,
                      job_list=False, older_machines=("Piast-Q",))
    addresses = (ADDRESS,)
    max_shots = SITE_MAX_SHOTS
    machine_qubits = 20               # data qubits by the PCSS specification; a read gives it
    max_ops = 2000                    # the longest circuit in the maker's public API 1.1.1
    seconds_kind = "wall"
    poll_seconds = 10.0
    default_machine = "AQT"
    collect_note = "Collect it the same day: how long the broker keeps a result is not published"
    lost_note = "The broker has no list of tasks: ask PCSS whether a task was made"
    # A 422 to the task request is a refusal, unless it is the upstream 429 of too many connections.
    refusal = Refusal(step="submit", codes=frozenset({422}), body=lambda body: not _busy(body))

    def __init__(self, token: str, machine: str | None = None, *,
                 transport: "httpx.BaseTransport | None" = None) -> None:
        super().__init__(token, machine, transport=transport)
        self._http = self.client(ADDRESS, {"X-API-Key": token}, timeout=30.0, max_connections=1)

    def _get(self, path: str, step: str, fields: bool = True) -> Any:
        try:
            return self._http.answer("GET", path, step=step, fields=fields)
        except SiteError as exc:
            if exc.status == 422 and _busy(exc.body):
                exc.busy = True               # a missed poll in the wait
            raise

    def read(self) -> dict:
        """One read of the machine list: the machine of the manifest is online when the broker names it."""
        names = (self._get("/machines", "read") or {}).get("names", [])
        if not isinstance(names, list):
            raise SiteError("the answer has no list of machine names", body=cut(names), step="read")
        return {"machine": self.machine, "machines": names, "online": self.machine in names,
                "qubits": self.machine_qubits}

    @classmethod
    def validate(cls, job: dict, read: dict | None) -> list[str]:
        """Offline: the problems of one job file against the schema of the broker and the limits of the class."""
        try:
            payload = payload_of(job["text"])
        except ValueError as exc:
            return [f"the file is not an operation list of the broker: {exc}"]
        return circuit_problems(payload, machine_qubits=cls.machine_qubits, max_ops=cls.max_ops) or unsendable(payload)

    def submit(self, job: dict, note: Note, prepared: object = None) -> str:
        """The one task request, which makes and runs the job. The answer is the uid of the task."""
        body = {"machine": self.machine, "payload": {"repetitions": job["shots"], **payload_of(job["text"])}}
        return self.submit_for_id(self._http, "/tasks", body, key="uid", what="task")

    def _job_get(self, path: str, step: str) -> Any:
        """A read of a job. The broker's answer that it does not know the job raises Expired, at any HTTP status."""
        said = f"the broker answered code {EXPIRED_CODE}, {EXPIRED_MESSAGE!r}"
        try:
            reply = self._get(path, step, fields=step == "status")        # `_counts` reads a result of any type
        except SiteError as exc:
            if _expired(exc.body):
                raise Expired(f"{exc}: {said}", status=exc.status, body=exc.body, url=exc.url, step=step) from None
            raise
        if _expired(reply):
            raise Expired(said, body=json.dumps(reply), step=step)
        return reply

    def status(self, job_id: object) -> JobState:
        """The state of a task as the broker names it: a state in DONE or FAILED ends the wait."""
        state = str((self._job_get(f"/tasks/{job_id}/status", "status") or {}).get("status", ""))
        if not state:
            raise SiteError("the answer has no status", step="status")
        low = state.lower()
        return JobState(state=state, final=low in DONE | FAILED, ok=low in DONE, configuring=False)

    def result(self, job_id: object) -> dict:
        """The counts of a task from its shots; the broker gives no seconds."""
        reply = self._job_get(f"/tasks/{job_id}/results", "result")
        return {"counts": _counts(reply), "seconds": None}
