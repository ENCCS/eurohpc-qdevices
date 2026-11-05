"""The fixed facts of the VLQ service: its addresses, job states, job kinds, files and long declared values.

The base path is doubled, /heappe/heappe, as in the public HEAppE interface document and service code.
"""

import base64
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Self

from ...values import is_int, sha256_hex
from ..facts import HIDDEN, Key, Rule

HEAPPE: Final = "https://quantum.heappe.it4i.cz/heappe/heappe"
USERORG: Final = "https://api.lexis.tech/userorg/api"
STATUS: Final = "https://quantum.heappe.it4i.cz/vlq-status.json"
STATUS_ROWS: Final = {"QPU_status": "QPU", "QCCW_status": "QCCSW", "queue_available": "Internal Scheduler",
                      "total_status": "Overall"}
STATES: Final = {1: "Configuring", 2: "Submitted", 4: "Queued", 8: "Running", 16: "Finished", 32: "Failed",
                 64: "Canceled", 128: "WaitingForServiceAccount", 256: "Deleted"}
CONFIGURING: Final = 1
_FINISHED: Final = 16
_WAITING_FOR_SERVICE_ACCOUNT: Final = 128
NOT_A_REFUSAL: Final = (401, 403, 408, 429)       # codes of 400 to 499 that say nothing of the circuit
NATIVE: Final = frozenset({"r", "prx", "cz", "move", "measure", "barrier"})

# The files of a job folder, each name written once, and the media types of the uploads.
TABLE_FILE: Final = "iqm_target_attrs.pkl"
ARTEFACTS: Final = ("backend.pkl", TABLE_FILE)            # made by the init job, uploaded to the metered job
CIRCUIT_FILE: Final = "circuit_0000.qasm"
TOKEN_FILE: Final = "user_token.enc"
RUN_KWARGS_FILE: Final = "run_kwargs.pkl"
RESULTS_FILE: Final = "results.pkl"
JOB_FILE: Final = "job.pkl"
RESULT_FILES: Final = (RESULTS_FILE, JOB_FILE)
PROGRESS_FILE: Final = "quantum_task_progress.log"
LOG_FILES: Final = ("stdout.txt", "stderr.txt", PROGRESS_FILE)
LOG_CHARACTERS: Final = 2000                              # the end of each log file that a failed line keeps
TEXT: Final = "text/plain"
BINARY: Final = "application/octet-stream"


@dataclass(frozen=True, slots=True, kw_only=True)
class HeappeState:
    """A HEAppE job state: its code, its name, and whether it ends the wait, is a success or is not yet submitted."""

    code: object
    name: str
    final: bool
    ok: bool
    configuring: bool

    @classmethod
    def of(cls, code: object) -> Self:
        """The state of a code; any code above Running ends the wait, except WaitingForServiceAccount.

        Only an int names a state: true and 1.0 equal 1 in Python, and would read as Configuring.
        """
        whole = is_int(code)
        return cls(code=code, name=(STATES.get(code) if whole else None) or f"unknown({code!r})",
                   final=whole and code > 8 and code != _WAITING_FOR_SERVICE_ACCOUNT,
                   ok=whole and code == _FINISHED, configuring=whole and code == CONFIGURING)


@dataclass(frozen=True, slots=True, kw_only=True)
class JobKind:
    """One of the two jobs of an order: its queue, command template, name, command, walltime and cores."""

    queue: str                # a node type of the cluster listing
    template: str             # a command template of that listing
    name: str
    command: str              # Q_COMMAND of the job's environment
    walltime: int             # its WalltimeLimit, unless the queue allows less
    cores: int                # MinCores and MaxCores of its one task


INIT_KIND: Final = JobKind(queue="init_queue", template="RunQInit", name="backend_init_job", command="backend_init",
                           walltime=60, cores=1)
RUN_KIND: Final = JobKind(queue="compute_queue", template="RunQExecute", name="backend_run_job",
                          command="backend_run", walltime=1800, cores=2)

# The long values of the profile of VLQ (site.py).
LEXIS_PROJECTS_KEY: Final = Key(name="lexis_projects", kind=list, default=())   # the LEXIS projects jobs may book on
LOGIN: Final = (
    "VLQ: get a LEXIS access token with the LEXIS Python client and a MyAccessID login, as IT4I's access",
    "page shows (https://docs.it4i.cz/en/docs/clusters/vlq/access). Keep it in a file of your own.",
    "A job needs 30 minutes or more left on the token, or twice wait_seconds when that is longer.",
    "qdevices check vlq shows the minutes left, without printing the token.",
)
BILLING: Final = Rule(
    "max(shots x 400 us, 0.9 s) per job (the guide's worst case), from the IT4I VLQ consumption guide "
    "(https://docs.it4i.cz/en/docs/clusters/vlq/vlq-consumption-guide). "
    "The device seconds a job reports can be below the 0.9 s floor; both are shown. "
    "Init jobs book classical node time only, shown apart",
    per_shot=400e-6,      # seconds, "approximately 400 us" a shot
    floor=0.9)

# Fernet text, and its base64 form, which the VLQ envelope file holds.
_FERNET: Final = re.compile(r"gAAAAA[A-Za-z0-9_=-]+")
_FERNET_B64: Final = re.compile(r"Z0FBQUFB[A-Za-z0-9+/=]+")

_Q: Final = r"\\?[\"']"               # a quote, or an escaped one in a JSON string
_VALUE: Final = r"[^\"'\\\s,}]+"
# The value of USER_JWT_PWD: assigned, in a JSON or Python pair, or in a job's name and value pair.
PASSWORD: Final = (
    re.compile(rf"(USER_JWT_PWD(?:{_Q})?\s*[:=]\s*(?:{_Q})?)({_VALUE})"),
    re.compile(rf"({_Q}Name{_Q}\s*:\s*{_Q}USER_JWT_PWD{_Q}\s*,\s*{_Q}Value{_Q}\s*:\s*{_Q})([^\"'\\]*)"),
    re.compile(rf"({_Q}Value{_Q}\s*:\s*{_Q})([^\"'\\]*)({_Q}\s*,\s*{_Q}Name{_Q}\s*:\s*{_Q}USER_JWT_PWD)"),
)
# The rows of the token filter in the order applied, after the JWT; a password match keeps all but the value.
SECRET_PATTERNS: Final = ((_FERNET_B64, HIDDEN), (_FERNET, HIDDEN), (PASSWORD[0], rf"\g<1>{HIDDEN}"),
                          (PASSWORD[1], rf"\g<1>{HIDDEN}"), (PASSWORD[2], rf"\g<1>{HIDDEN}\g<3>"))


def token_expiry(token: str) -> float | None:
    """The expiry (seconds since the epoch) of a JWT, from its claim; None if it cannot be read or is not finite."""
    try:
        part = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        expiry = float(claims["exp"])
    except Exception:
        return None
    return expiry if math.isfinite(expiry) else None


def lexis_problems(man: dict, site_config: dict) -> list[str]:
    """The LEXIS project of a manifest against lexis_projects in qdevices.toml, as the device time is booked on it."""
    if man["lexis_project"] in site_config["lexis_projects"]:
        return []
    return [f"the LEXIS project {man['lexis_project']!r} is not listed in lexis_projects for {man['site']} in "
            "qdevices.toml: the device time is booked on it, and no flag changes it"]


def digests(files: Mapping[str, bytes]) -> dict[str, dict]:
    """The size and the SHA-256 digest of each file, by its name, in the order given."""
    return {name: {"bytes": len(data), "sha256": sha256_hex(data)} for name, data in files.items()}
