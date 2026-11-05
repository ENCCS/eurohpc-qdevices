"""Euro-Q-Exa at LRZ, over plain HTTP to the Munich Quantum Portal (MQSS REST interface).

The circuit field is the text of a list of one circuit, as the public reference clients send it.
"""

import ast
import json
import re
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from ..qasm import Qasm
from ..values import too_deep
from . import local_time, loci
from .base import Site, SiteError, cut
from .facts import Profile, Rule
from .protocol import JobState, Note, Refusal

if TYPE_CHECKING:
    import httpx

ADDRESS: Final = "https://portal.quantum.lrz.de:4000/v1"
DONE: Final = frozenset({"COMPLETED"})
FAILED: Final = frozenset({"FAILED", "CANCELLED", "CANCELED"})
_REFUSAL_WORDS: Final = re.compile(r"\b(?:cz|pair|coupler|direction|locus|loci|qubit|no_modify|gate(?!way)|native)",
                                   re.IGNORECASE)
_ALWAYS: Final = frozenset({"measure", "barrier"})
_PROGRAM: Final = re.compile(r"\bOPENQASM\s+[0-9]")      # the version line that opens each OpenQASM program
COMPILED: Final = "without no_modify the site compiles the circuit, so its own count of gates can be higher"
LOGIN: Final = (
    "Euro-Q-Exa: make a token on the Tokens page of the Munich Quantum Portal, https://portal.quantum.lrz.de.",
    "On a 403, check that you can log in to the portal before you make a new token.",
)
BILLING: Final = Rule(
    "EuroHPC time on Euro-Q-Exa is billed in wall-clock QPU seconds (LRZ); LRZ also defines a unit "
    "for its quantum systems, the equivalent qubit-second; the records give the seconds from "
    "scheduled to completed")


def _literal(value: object) -> object:
    if isinstance(value, str):
        try:
            found = ast.literal_eval(value)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            return None
        return None if too_deep(found) else found
    return value


def _is_utf8(data: bytes) -> bool:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _plain(value: object) -> object:
    """A value in a form JSON takes: the site lists a gate with a table whose keys are tuples."""
    if isinstance(value, dict):
        return {k if isinstance(k, str) else str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, set):                    # a set has no order: its entries sorted, so no hash order
        try:
            return [_plain(v) for v in sorted(value)]
        except TypeError:                         # entries of types that do not compare
            return [_plain(v) for v in sorted(value, key=repr)]
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value if value is None or isinstance(value, (bool, int, float, str)) else str(value)


def _gate_names_of(instructions: object) -> list[str]:
    names = set()
    for entry in instructions if isinstance(instructions, (list, tuple, dict)) else []:
        if isinstance(entry, (list, tuple)) and entry:
            entry = entry[0]
        if isinstance(entry, str):
            names.add(entry)
    return sorted(names)


class EuroQExa(Site):
    """The machines of Euro-Q-Exa, where one request makes and runs a job."""

    name = "euroqexa"
    token_env = "MQSS_TOKEN"
    profile = Profile(title="Euro-Q-Exa", operator="LRZ", login=LOGIN, billing=BILLING, older_machines=("EQE1",))
    addresses = (ADDRESS,)
    options = MappingProxyType({"no_modify": bool})
    max_shots_times_gates = 3_000_000  # the most shots times gate operations of a job (LRZ)
    seconds_kind = "scheduled_to_completed"
    layout_pin = True                 # the read gives layout_sha256 (loci.layout_of)
    refusal = Refusal(step="submit", codes=frozenset({400, 422}), body=lambda text: _REFUSAL_WORDS.search(text or ""))

    def __init__(self, token: str, machine: str | None = None, *,
                 transport: "httpx.BaseTransport | None" = None) -> None:
        super().__init__(token, machine, transport=transport)
        self._http = self.client(ADDRESS, {"Authorization": f"Bearer {token}"}, timeout=30.0)
        self._sent: dict[str, str | None] = {}    # job id -> the app's submitted_utc, to read the result's stamps

    def read(self) -> dict:
        """One read of the machine with its layout; with no machine, the qubits and state of each resource."""
        if not self.machine:
            listed = self._http.answer("GET", "resources", step="read", fields=True)
            return {"resources": {name: {"qubits": e.get("qubits"), "online": e.get("online")}
                                  for name, e in (listed or {}).items() if isinstance(e, dict)}}
        entry = self._http.answer("GET", f"resources/{self.machine}", step="read", fields=True) or {}
        pending = self._http.answer("GET", f"resources/{self.machine}/num_pending_jobs", step="read", fields=True)
        instructions = _plain(_literal(entry.get("instructions")))
        read = {"machine": entry.get("name", self.machine), "qubits": entry.get("qubits"),
                "online": entry.get("online"), "connectivity": _plain(_literal(entry.get("connectivity"))),
                "instructions": instructions, "gate_names": _gate_names_of(instructions),
                "pending_jobs": (pending or {}).get("num_pending_jobs")}
        return {**read, **loci.layout_of(read)}

    @classmethod
    def validate(cls, job: dict, read: dict | None) -> list[str]:
        """The problems of one job: its text and qubits, and with no_modify its gates and pairs against the read."""
        text = Site.text_of(job)
        parsed = Qasm.parse(text)
        problems = [] if _is_utf8(job["text"]) else ["the file is not UTF-8 text"]       # submit decodes strictly
        problems += [] if "OPENQASM" in text else ["the file is not an OpenQASM text"]
        if (programs := len(_PROGRAM.findall(parsed.clean))) > 1:            # the joined --qasm of several jobs
            problems.append(f"the file holds {programs} OpenQASM programs: a file to send holds one job")
        qubits = parsed.qubit_problems(read)
        problems += qubits
        if job["options"].get("no_modify") and read and read.get("gate_names"):
            outside = sorted(parsed.gate_names - set(read["gate_names"]) - _ALWAYS)
            if outside:
                problems.append(f"with no_modify the gates {outside} are not among the gates of the machine "
                                f"({', '.join(read['gate_names'])})")
        if job["options"].get("no_modify") and read and not qubits:       # no pair check past a qubit problem
            problems += loci.pair_check(parsed, read)[0]
        return problems

    @staticmethod
    def notes(job: dict, read: dict | None) -> list[str]:
        """With no_modify: a pair listed only the other way round, or why the pairs were not checked."""
        if not (job["options"].get("no_modify") and read):
            return []
        parsed = Qasm.parse(Site.text_of(job))
        if parsed.qubit_problems(read):
            return []
        return loci.pair_check(parsed, read)[1]

    @staticmethod
    def count_notes(job: dict) -> list[str]:
        """Offline: the note on the gate count of a job without no_modify, whose text the site compiles."""
        return [] if job["options"].get("no_modify") else [COMPILED]

    def submit(self, job: dict, note: Note, prepared: object = None) -> str:
        """The one request that makes and runs a job. The answer is its uuid."""
        body = {"circuit": str([job["text"].decode("utf-8")]), "circuit_format": "qasm",
                "resource_name": self.machine, "shots": job["shots"],
                "no_modify": bool(job["options"].get("no_modify", False)), "queued": False}
        return self.submit_for_id(self._http, "job", body, key="uuid", what="job")

    def status(self, job_id: object) -> JobState:
        """The state of a job, upper-cased: COMPLETED and the states in FAILED end the wait."""
        reply = self._http.answer("GET", f"job/{job_id}/status", step="status", fields=True)
        state = str((reply or {}).get("status", "")).upper()
        if not state:
            raise SiteError("the answer has no status", body=cut(reply), step="status")
        return JobState(state=state, final=state in DONE | FAILED, ok=state in DONE, configuring=False)

    def result(self, job_id: object) -> dict:
        """The counts of a job, its seconds read from the stamps of the site, and the three stamps as given."""
        reply = self._http.answer("GET", f"job/{job_id}/result", step="result")
        if not isinstance(reply, dict) or "result" not in reply:
            raise SiteError("the answer has no result field", body=cut(reply), step="result")
        raw = reply["result"]
        try:
            counts = json.loads(raw) if isinstance(raw, str) else raw
            if too_deep(counts):                    # the lines after it recurse once a level
                raise ValueError
        except (ValueError, RecursionError):
            raise SiteError("the result field is not JSON", body=cut(raw), step="result") from None
        times = local_time.site_times(reply, self._sent.get(str(job_id)))
        return {"counts": counts, **times, **{key: reply.get(key) for key in local_time.STAMPS}}

    def sent_at(self, job_id: object, submitted_utc: str | None) -> None:
        """The app's own submitted_utc of a job, which the stamps of its result are read against."""
        self._sent[str(job_id)] = submitted_utc

    def logs(self, job_id: object) -> dict:
        """The reason the site gives for the end of a failed job, cut; empty when it cannot be read."""
        try:
            return {"cancel_reason": cut(self._http.request("GET", f"job/{job_id}/cancel_reason", step="logs").text)}
        except SiteError:
            return {}
