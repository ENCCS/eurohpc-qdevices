"""The shared values and helpers of the tests: a token, a text, a config, a fake clock, a manifest and a send."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from qdevices import config, runner
from qdevices.paths import Places

TOKEN = "tok-" + "A1b2C3d4" * 6           # synthetic, never a real token
QASM = b'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\ncreg c[1];\nx q[0];\nmeasure q -> c;\n'
CONFIG = """
[euroqexa]
projects = ["TEST-PROJECT"]
budget_seconds = 1000
job_seconds_limit = 100
wait_seconds = 60

[vlq]
projects = ["TEST-PROJECT"]
lexis_projects = ["TEST-LEXIS"]
budget_seconds = 1000
job_seconds_limit = 100
wait_seconds = 60

[piastq]
projects = ["TEST-PROJECT"]
budget_seconds = 1000
job_seconds_limit = 100
wait_seconds = 60
"""


@dataclass(slots=True, eq=False)
class FakeClock:
    """A clock that moves only when it sleeps: `t` seconds after `start`."""

    t: float = 0.0
    start: datetime = datetime(2026, 1, 5, 12, 0, 0, tzinfo=UTC)    # a Monday

    def utc(self) -> datetime:
        return self.start + timedelta(seconds=self.t)

    def monotonic(self) -> float:
        return self.t

    def sleep(self, seconds: float) -> None:
        self.t += seconds


def turn(answers: list):
    """The next of the answers in turn; the last one stays."""
    return answers.pop(0) if len(answers) > 1 else answers[0]


def places_in(tmp: Path) -> Places:
    return Places(records=tmp / "records", reads=tmp / "reads", state=tmp / "state", config=tmp / "qdevices.toml")


def cfg(text: str = CONFIG) -> dict:
    return config.parse(text)


def write_manifest(folder: Path, site: str = "euroqexa", jobs=(("J1", 10), ("J2", 10), ("J3", 10)),
                   text: bytes = QASM, **extra) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    entries = []
    for order, (name, shots) in enumerate(jobs, 1):
        (folder / f"{name}.qasm").write_bytes(text)
        entries.append({"order": order, "name": name, "file": f"{name}.qasm",
                        "sha256": hashlib.sha256(text).hexdigest(), "shots": shots})
    head = {"format": "qdevices/1", "site": site, "machine": "M1", "project": "TEST-PROJECT"}
    if site == "vlq":
        head.update(lexis_project="TEST-LEXIS", resource="R1")
    path = folder / "manifest.json"
    path.write_text(json.dumps({**head, **extra, "jobs": entries}))
    return path


def lines_of(path: Path) -> list[dict]:
    return [json.loads(row) for row in Path(path).read_text().splitlines() if row.strip()]


def records_of(places: Places) -> list[Path]:
    return sorted(Path(places.records).rglob("run_*.jsonl"))


def events(path: Path, kind: str) -> list[dict]:
    return [line for line in lines_of(path) if line["event"] == kind]


def send(manifest: Path, site, places: Places, clock: FakeClock, conf=None, *, host="host-a", **kw) -> int:
    return runner.send(manifest, site, cfg=conf or cfg(), places=places, clock=clock, sleep=clock.sleep, host=host,
                       say=lambda *a, **k: None, **kw)
