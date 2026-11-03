"""Emulate an example on your own computer, with the Python standard library alone: no account, and nothing is sent.

The noise is a simple model for learning, not a model of any machine. It needs Python 3.8 or later.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from circuit import Circuit, circuit_of

QRISP_FILE = "qrisp_emulated.json"
QUTIP_FILE = "qutip_emulated.json"


def jobs_of(folder: Path) -> list:
    """The jobs of a folder, as its manifest.json lists them."""
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"]


def came_back(folder: Path) -> dict:
    """The counts of each job in a folder's results.json; nothing if it has not run."""
    path = folder / "results.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def stored(folder: Path, name: str) -> dict:
    """The shares of each job on another emulator, as a folder stores them in the file `name`; nothing if none."""
    path = folder / name
    return json.loads(path.read_text(encoding="utf-8"))["jobs"] if path.exists() else {}


def qrisp_stored(folder: Path) -> dict:
    """The shares of each job on Qrisp's emulator; nothing if the folder holds none."""
    return stored(folder, QRISP_FILE)


def qutip_stored(folder: Path) -> dict:
    """The shares of each job on QuTiP, by qutip-qip; nothing if the folder holds none."""
    return stored(folder, QUTIP_FILE)


def top(shares: dict, most: int = 6) -> str:
    """The keys with the largest shares, as a line."""
    rows = sorted(shares.items(), key=lambda kv: (-round(kv[1], 9), kv[0]))[:most]
    more = f"  and {len(shares) - most} more" if len(shares) > most else ""
    return "  ".join(f"{key}: {value:.3f}" for key, value in rows) + more


def fractions(counts: dict) -> dict:
    """Counts as shares."""
    total = sum(counts.values())
    return {key: n / total for key, n in counts.items()}


@dataclass(frozen=True)
class Report:
    """Each job of a manifest: a perfect machine, Qrisp's and QuTiP's stored shares, noise if asked, the machine."""

    manifest: Path
    shots: int = 0
    noise: float = 0.0
    readout: float = 0.0
    seed: int = 1

    def _emulated(self, circuit: Circuit, job: dict) -> list:
        if not (self.shots or self.noise or self.readout):
            return []
        drawn = self.shots or max(job["shots"], 1000)
        label = "emulated, with noise" if self.noise or self.readout else "emulated shots"
        counts = circuit.sample(drawn, self.noise, self.readout, self.seed)
        return [f"  {label} ({drawn} shots, seed {self.seed})  {top(fractions(counts))}"]

    def _job(self, job: dict, back: dict, others: dict) -> list:
        circuit = circuit_of(self.manifest.parent / job["file"])
        machine = [f"  the machine, once  {top(fractions(back[job['name']]))}"] if job["name"] in back else []
        stored = [f"  {label}, stored, no noise  {top(held[job['name']])}" for label, held in others.items()
                  if job["name"] in held]
        return [f"{job['name']}: {circuit.size}", f"  a perfect machine  {top(circuit.shares())}", *stored,
                *self._emulated(circuit, job), *machine]

    def lines(self) -> list:
        """One block of lines for each job."""
        folder = self.manifest.parent
        others = {"Qrisp's emulator": qrisp_stored(folder), "QuTiP": qutip_stored(folder)}
        jobs = json.loads(self.manifest.read_text(encoding="utf-8"))["jobs"]
        return [line for job in jobs for line in self._job(job, came_back(folder), others)]

    def __str__(self) -> str:
        """The lines as one text."""
        return "\n".join(self.lines())


def _report(argv: list | None) -> Report:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--shots", type=int, default=0, help="the shots of a noisy run (default: at least 1000)")
    parser.add_argument("--noise", type=float, default=0.0, help="the chance of an error after a two-qubit gate; above "
                        "1000 shots it still takes 1000 random runs")
    parser.add_argument("--readout", type=float, default=0.0, help="the chance that a bit reads wrong")
    parser.add_argument("--seed", type=int, default=1, help="the same seed gives the same counts")
    args = parser.parse_args(argv)
    if not (0 <= args.noise <= 1 and 0 <= args.readout <= 1) or args.shots < 0:
        parser.error("--noise and --readout are chances from 0 to 1, so 0.03 means 3 per cent; --shots is not negative")
    return Report(args.manifest, args.shots, args.noise, args.readout, args.seed)


def main(argv: list | None = None) -> int:
    """Print the report of one manifest."""
    print(_report(argv))
    print("Emulated on this computer: nothing was sent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
