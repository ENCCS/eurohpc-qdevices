"""The hydrogen molecule by phase estimation: how the numbers read, and what a run gave. `with_qrisp.py` makes them."""

import json
from dataclasses import asdict, dataclass
from math import pi
from pathlib import Path
from typing import Final

STORED: Final = Path(__file__).with_name("reference_curve.json")
STRONG: Final = 0.1         # the nearest point of the grid holds at least 0.405 of the share of a level


def stored_numbers() -> dict:
    """All that reference_curve.json holds."""
    return json.loads(STORED.read_text(encoding="utf-8"))


def keep_numbers(held: dict) -> None:
    """Write reference_curve.json, in the one form whose digest a test holds."""
    STORED.write_text(json.dumps(held, indent=1) + "\n", encoding="utf-8")


def energy_of(phase: float) -> float:
    """At t = 1 the register holds the phase of exp(-iE), so E = -2 pi phase, for E from -2 pi to 0."""
    return -2 * pi * phase


def lowest_strong_peak(found: dict[float, float], bits: int) -> float:
    """The rule of reading: of the peaks with at least STRONG of the shots, the phase of the lowest energy."""
    size = 2 ** bits
    share = [found.get(m / size, 0.0) for m in range(size)]
    return max(m for m in range(size)
               if share[m] >= STRONG and share[m] >= max(share[m - 1], share[(m + 1) % size])) / size


@dataclass(frozen=True, slots=True)
class Size:
    """One size of phase estimation: its bits, its qubits, its two-qubit gates, and the phase it read most often."""

    bits: int
    qubits: int
    gates: int
    phase: float

    @property
    def energy(self) -> float:
        """The energy of its phase, for the electrons alone."""
        return energy_of(self.phase)

    def __str__(self) -> str:
        """The line of the table."""
        return f"{self.bits:>4} {self.qubits:>7} {self.gates:>16} {self.phase:>10.4f} {self.energy:>7.3f}"


@dataclass(frozen=True, slots=True)
class Estimates:
    """The exact energy, each size, and the share of each energy at the largest size."""

    exact: float
    sizes: tuple[Size, ...]
    energies: dict[float, float]

    def table(self) -> str:
        """The exact energy, then one line for each size."""
        head = "bits  qubits  two-qubit gates  top phase  energy"
        return "\n".join([f"The exact energy: {self.exact:.3f} hartree", head, *map(str, self.sizes)])


MADE: Final = Estimates(-1.857,
                        (Size(3, 5, 261, 0.25), Size(4, 6, 558, 0.3125), Size(5, 7, 1142, 0.28125),
                         Size(6, 8, 2307, 0.296875)),
                        {-1.865: 0.9631, -0.196: 0.0095, -1.767: 0.0087, -1.963: 0.0062, -1.669: 0.002, -0.295: 0.0017,
                         -2.062: 0.0017, -1.571: 0.0009, -2.16: 0.0008, -0.098: 0.0005})


@dataclass(frozen=True, slots=True)
class Point:
    """One bond length of a run: the block's numbers, then the lowest strong peak and the top reading, as phases."""

    length: float
    nuclear: float
    exact: float
    overlap: float
    phase: float
    share: float
    top_phase: float
    top_share: float

    @property
    def energy(self) -> float:
        """The reading by the rule, with the nuclei."""
        return energy_of(self.phase) + self.nuclear

    @property
    def top(self) -> float:
        """The top reading, with the nuclei."""
        return energy_of(self.top_phase) + self.nuclear

    def __str__(self) -> str:
        """The line of the table."""
        return (f"{self.length:>6} {self.exact:>9.4f} {self.overlap:>8.3f} {self.energy:>8.3f} {self.share:>6.3f} "
                f"{self.top:>8.3f} {self.top_share:>6.3f}")


@dataclass(frozen=True, slots=True)
class Curve:
    """A run of phase estimation over bond lengths: the same gates at each length, with other angles."""

    bits: int
    steps: int
    qubits: int
    gates: int
    qrisp: str
    points: tuple[Point, ...]

    @classmethod
    def stored(cls) -> "Curve":
        """The run that reference_curve.json holds, for a page with no Qrisp."""
        held = stored_numbers()["emulated"]
        return cls(**{**held, "points": tuple(Point(**point) for point in held["points"])})

    @property
    def grid(self) -> float:
        """The step of the grid of energies, in hartree."""
        return 2 * pi / 2 ** self.bits

    def at(self, length: float) -> Point:
        """The point at a bond length."""
        return {point.length: point for point in self.points}[length]

    def store(self) -> None:
        """Keep this run in reference_curve.json, and leave its other keys as they are."""
        held = stored_numbers()
        held["emulated"] = asdict(self)
        keep_numbers(held)

    def table(self) -> str:
        """What the run is, then one line for each length. Energies are in hartree, with the nuclei."""
        head = "length     exact  overlap  reading  share      top  share"
        return "\n".join([f"{self.bits} bits, {self.steps} steps per unit time: {self.qubits} qubits, "
                          f"{self.gates} two-qubit gates, grid step {self.grid:.3f} hartree", head,
                          *map(str, self.points)])
