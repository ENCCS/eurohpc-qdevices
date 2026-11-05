"""One example folder on disk: its manifest, its README and its three scripts."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from readme import Readme

TOOLS = Path(__file__).resolve().parent
SCRIPT_MODELS = {"emulate_one.sh": "emulate.sh", "run_one.sh": "run.sh", "submit_one.sh": "submit.sh"}
KEPT = ("results.json", "qrisp_emulated.json", "qutip_emulated.json", "circuit.png", "outcomes.png",  # not by a writer
        "emulate_qutip.py", "emulate_qrisp.py")


def manifest_text(head: dict, jobs: list) -> str:
    """The manifest in the layout of the examples: one line per job."""
    lines = [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in head.items()]
    rows = ",\n".join(f"    {json.dumps(job)}" for job in jobs)
    return "{\n" + "\n".join(lines) + '\n  "jobs": [\n' + rows + "\n  ]\n}\n"


@dataclass(frozen=True)
class ExampleFolder:
    """A folder on disk, and its name under examples/, which its README gives."""

    path: Path
    name: str

    def write_manifest(self, head: dict, jobs: list) -> Path:
        """Write manifest.json; its path."""
        self.path.mkdir(parents=True, exist_ok=True)
        path = self.path / "manifest.json"
        path.write_text(manifest_text(head, jobs), encoding="utf-8")
        return path

    def write_page(self, page: Readme) -> None:
        """Write README.md and copy the three scripts."""
        self.path.mkdir(parents=True, exist_ok=True)
        (self.path / "README.md").write_text(page.text(self.name, self.path), encoding="utf-8")
        for model, script in SCRIPT_MODELS.items():
            shutil.copy(TOOLS / model, self.path / script)
