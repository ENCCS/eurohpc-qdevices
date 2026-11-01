"""Write the Qrisp examples as OpenQASM 2 files and one qdevices manifest each, for Euro-Q-Exa.

    pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples      # into examples/qrisp/<name>/
    pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples --project YOURS --out my-runs

It needs Qrisp (the pixi workspace in this folder) and makes no network call. The site compiles the text,
so the manifest does not set `no_modify`. Then: `qdevices dry-run <folder>/manifest.json`.
"""

import argparse
import json
import os
import platform
import shutil
from pathlib import Path
from typing import Final

from qasm2 import to_qasm2

from qdevices.manifest import FORMAT
from qdevices.values import sha256_hex

# NumPy's AVX-512 code puts some angles of Qrisp one bit apart; without it every x86 machine writes the same text.
if platform.machine().lower() in ("x86_64", "amd64"):
    os.environ.setdefault("NPY_DISABLE_CPU_FEATURES", "X86_V4 AVX512_ICL AVX512_SPR")
from programs import PROGRAMS, Program  # after the line above: NumPy reads it on import

HERE: Final = Path(__file__).resolve().parent


def manifest_text(head: dict, jobs: list[dict]) -> str:
    """The manifest in the layout of the other examples: one line per job."""
    lines = [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in head.items()]
    rows = ",\n".join(f"    {json.dumps(job)}" for job in jobs)
    return "{\n" + "\n".join(lines) + '\n  "jobs": [\n' + rows + "\n  ]\n}\n"


def write_one(program: Program, folder: Path, *, machine: str, project: str, shots: int) -> Path:
    """Write the text of one program and its manifest of one job into a folder; the path of the manifest."""
    text = to_qasm2(program.circuit()).encode("utf-8")
    folder.mkdir(parents=True, exist_ok=True)
    file = f"{program.name}.qasm"
    (folder / file).write_bytes(text)
    head = {"format": FORMAT, "site": "euroqexa", "machine": machine, "project": project,
            "made_with": "Qrisp, examples/qrisp/write_manifests.py", "ideal": program.ideal}
    job = {"order": 1, "name": program.name, "file": file, "sha256": sha256_hex(text), "shots": shots}
    path = folder / "manifest.json"
    path.write_text(manifest_text(head, [job]), encoding="utf-8")
    shutil.copy(HERE / "run_one.sh", folder / "run.sh")
    return path


def main(argv: list[str] | None = None) -> int:
    """Write each program of PROGRAMS into a folder of its own, and print one line for each."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE, help="the folder of the example folders")
    parser.add_argument("--machine", default="EQE1")
    parser.add_argument("--project", default="MY-PROJECT")
    parser.add_argument("--shots", type=int, help="the shots of every job (default: 100, and 1000 for the eight from "
                                                  "the pages of Qrisp, as they ran)")
    args = parser.parse_args(argv)
    for program in PROGRAMS:
        path = write_one(program, args.out / program.name.lower(), machine=args.machine,
                         project=args.project, shots=args.shots or program.shots)
        print(f"{program.name:<18} {program.what}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
