"""What the machine read: the counts as shares, with shot errors, and a simple model of a loss at each gate.

Python's standard library alone.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

KEYS = 4                                   # the keys of two qubits


@dataclass(frozen=True)
class Read:
    """The counts of one job."""

    counts: dict

    @property
    def shots(self) -> int:
        """All the shots."""
        return sum(self.counts.values())

    def share(self, key: str) -> float:
        """The share of the shots with a key."""
        return self.counts.get(key, 0) / self.shots

    def error(self, key: str) -> float:
        """The shot error of that share: the binomial standard error."""
        share = self.share(key)
        return sqrt(share * (1 - share) / self.shots)


def reads(folder: Path) -> dict:
    """The counts of each job in a folder's results.json."""
    counts = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    return {name: Read(job) for name, job in counts.items()}


@dataclass(frozen=True)
class SameLoss:
    """A simple model, ours: each two-qubit gate keeps the answer with the same chance, set by one job.

    A shot it loses lands on any key with equal chance. By default it puts all the loss on those gates; `readout` is
    the chance that the readout keeps a shot, and a shot it loses lands in the same way.
    """

    perfect: float                         # the share of the key on a perfect machine, in the job that sets it
    read: float                            # the share the machine read
    gates: int                             # the two-qubit gates of that job
    readout: float = 1.0                   # the chance that the readout keeps a shot

    @property
    def kept(self) -> float:
        """The chance that one two-qubit gate keeps the answer."""
        return ((self.read - 1 / KEYS) / (self.readout * (self.perfect - 1 / KEYS))) ** (1 / self.gates)

    def share(self, perfect: float, gates: int) -> float:
        """The share this model gives a job with that perfect share, if all its two-qubit gates run."""
        return self.readout * self.kept**gates * (perfect - 1 / KEYS) + 1 / KEYS
