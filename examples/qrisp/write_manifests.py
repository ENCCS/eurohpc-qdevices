"""Write the Qrisp examples as OpenQASM 2 files, one folder each, for Euro-Q-Exa: `qrisp-examples` in this pixi.toml.

It makes no network call. The site compiles the text, so the manifest does not set `no_modify`.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from notes import NOTES
from programs import PROGRAMS, Program
from qasm2 import to_qasm2

from qdevices.manifest import FORMAT
from qdevices.values import sha256_hex

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from circuit import Circuit
from emulate import top
from example_folder import ExampleFolder
from readme import Readme

HERE: Final = Path(__file__).resolve().parent
MADE_BY: Final = ("Written by `examples/qrisp/write_manifests.py` from `programs.py`. To change the circuit, change "
                  "the function, and from the top of the clone run `pixi run --manifest-path examples/qrisp/pixi.toml "
                  "qrisp-examples`: a text changed by hand no longer matches its SHA-256.")
PERFECT: Final = ("{ideal}. `./emulate.sh` and the site print keys, with the highest qubit on the left: {keys}. "
                  "Qrisp's own labels, as a Qrisp program prints them, read q[0] first, so a label and its key can "
                  "look reversed. The line of Qrisp's emulator in `./emulate.sh` is in keys.")


def page_of(program: Program, file: str, text: str) -> Readme:
    """The README of one program, with the keys its text gives."""
    note = NOTES[program.name]
    perfect = PERFECT.format(ideal=program.ideal, keys=top(Circuit.of_text(text).shares(), 4))
    return Readme("euroqexa", note.title, note.about, note.steps, perfect, note.back, (file,), made_by=MADE_BY)


@dataclass(frozen=True, slots=True)
class Writer:
    """Where the folders go, for which machine and project, and the shots of every job if not each program's own."""

    out: Path
    machine: str
    project: str
    shots: int | None

    def write(self, program: Program) -> Path:
        """Write one folder: the text, the manifest of one job, the README and the scripts; the path of the manifest."""
        folder = ExampleFolder(self.out / program.name.lower(), f"qrisp/{program.name.lower()}")
        text, file = to_qasm2(program.circuit()), f"{program.name}.qasm"
        head = {"format": FORMAT, "site": "euroqexa", "machine": self.machine, "project": self.project,
                "made_with": "Qrisp, examples/qrisp/write_manifests.py", "ideal": program.ideal}
        job = {"order": 1, "name": program.name, "file": file, "sha256": sha256_hex(text.encode("utf-8")),
               "shots": self.shots or program.shots}
        path = folder.write_manifest(head, [job])
        (folder.path / file).write_bytes(text.encode("utf-8"))
        folder.write_page(page_of(program, file, text))
        return path


def main(argv: list[str] | None = None) -> int:
    """Write each program of PROGRAMS into a folder of its own, and print one line for each."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE, help="the folder of the example folders")
    parser.add_argument("--machine", default="EQE1")
    parser.add_argument("--project", default="MY-PROJECT")
    parser.add_argument("--shots", type=int, help="the shots of every job (default: each program's own, as they ran)")
    args = parser.parse_args(argv)
    writer = Writer(args.out, args.machine, args.project, args.shots)
    for program in PROGRAMS:
        print(f"{program.name:<18} {program.what}: {writer.write(program)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
