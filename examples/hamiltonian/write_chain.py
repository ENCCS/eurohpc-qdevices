"""Write the chain as OpenQASM 2 texts and manifests, for Euro-Q-Exa: `hamiltonian` in examples/qrisp/pixi.toml.

It makes no network call. With `--project YOURS --out my-chain` it makes your own copy.
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from chain import Steps, T, closed_form, control

from qdevices.manifest import FORMAT
from qdevices.qasm import Qasm
from qdevices.values import sha256_hex

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "qrisp"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from chain_notes import LIVE_PAGE, page_of_all
from circuit import shares_of
from example_folder import ExampleFolder
from programs import Program
from qasm2 import to_qasm2
from readme import Readme
from with_qrisp import chain_by_qrisp

HERE: Final = Path(__file__).resolve().parent
ZERO: Final = {"000": 1.0}
SMALL: Final = "a small function"           # Steps or control of chain.py, which write a text with no package


def by_qrisp(t: float, steps: int) -> str:
    """Qrisp's one line for the same Hamiltonian and start, written by qasm2.py."""
    return to_qasm2(Program("QRISP", "", "", lambda: chain_by_qrisp(t, steps)).circuit())


def rounded(shares: dict[str, float]) -> dict[str, float]:
    """Shares to six places, without the keys that hold none."""
    return {key: round(v, 6) for key, v in sorted(shares.items()) if v > 1e-6}


@dataclass(frozen=True, slots=True)
class Job:
    """One job: its name, text, the time it stands for, its steps, the key that answers it, and its shots."""

    name: str
    text: str
    time: str
    t: float
    steps: int
    key: str = "100"
    shots: int = 1000
    excitations: int = 1
    made: str = SMALL                   # what made its text: SMALL, or Qrisp for the job QRISP

    def line(self, order: int, folder: Path, shots: int | None) -> dict:
        """Write the text and give the line of the manifest; the app copies its own keys to the record."""
        data = self.text.encode("utf-8")
        (folder / f"{self.name}.qasm").write_bytes(data)
        return {"order": order, "name": self.name, "file": f"{self.name}.qasm", "sha256": sha256_hex(data),
                "shots": shots or self.shots, "time": self.time, "steps": self.steps,
                "gates": Qasm.parse(self.text).gate_count,
                "two_qubit": sum(line.startswith(("cx ", "cz ")) for line in self.text.splitlines()),
                "key": self.key, "excitations": self.excitations,
                "exact_shares": rounded(closed_form(self.t) if self.excitations else ZERO),
                "text_shares": rounded(shares_of(self.text))}


def jobs() -> tuple[Job, ...]:
    """The jobs in the order they go: the answer first, so a small budget still reaches it."""
    hand = Steps(T, 2).text()
    return (Job("CONTROL", control(), "0", 0.0, 0, "001", 100),
            Job("MAIN", hand, "T", T, 2),
            Job("QRISP", by_qrisp(T, 2), "T", T, 2, made="Qrisp"),
            Job("REPEAT", hand, "T", T, 2),
            Job("HALF", Steps(T / 2, 2).text(), "T/2", T / 2, 2, "010"),
            Job("BACK", Steps(2 * T, 4).text(), "2T", 2 * T, 4, "001"),
            Job("ZERO", Steps(T, 2, excited=False).text(), "T", T, 2, "000", excitations=0),
            Job("STEPS1", Steps(T, 1).text(), "T", T, 1),
            Job("STEPS4", Steps(T, 4).text(), "T", T, 4),
            Job("STEPS8", Steps(T, 8).text(), "T", T, 8),
            Job("ORDER1", Steps(T, 2, 1).text(), "T", T, 2))


def made_with(chosen: tuple[Job, ...]) -> str:
    """The made_with of a manifest: what made the texts of its jobs, Qrisp first, then this writer."""
    makers = sorted({job.made for job in chosen}, key=lambda made: (made != "Qrisp", made))
    return f"{' and '.join(makers)}, examples/hamiltonian/write_chain.py"


@dataclass(frozen=True, slots=True)
class Writer:
    """Where the folders go, for which machine and project, and the shots of every job if not each job's own."""

    out: Path
    machine: str
    project: str
    shots: int | None

    def folder(self, name: str, chosen: tuple[Job, ...], page: Readme) -> Path:
        """Write one folder: the texts, the manifest, the README and the scripts; the path of the manifest."""
        folder = ExampleFolder(self.out / name, f"hamiltonian/{name}")
        head = {"format": FORMAT, "site": "euroqexa", "machine": self.machine, "project": self.project,
                "made_with": made_with(chosen), "ideal": "keys read q[2] q[1] q[0]: 001 at the start, 100 on arrival"}
        folder.path.mkdir(parents=True, exist_ok=True)
        path = folder.write_manifest(head, [job.line(n, folder.path, self.shots) for n, job in enumerate(chosen, 1)])
        folder.write_page(page)
        return path

    def write(self) -> Path:
        """Write the job for a talk and all the jobs; the path of the manifest of all the jobs."""
        every = jobs()
        self.folder("live", tuple(job for job in every if job.name == "MAIN"), LIVE_PAGE)
        return self.folder("state_transfer", every, page_of_all(len(every)))


def main(argv: list[str] | None = None) -> int:
    """Write the folders of the chain and print the path of the manifest of all the jobs."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE)
    parser.add_argument("--machine", default="EQE1")
    parser.add_argument("--project", default="MY-PROJECT")
    parser.add_argument("--shots", type=int, help="the shots of every job (default: 1000, and 100 for CONTROL)")
    args = parser.parse_args(argv)
    print(Writer(args.out, args.machine, args.project, args.shots).write())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
