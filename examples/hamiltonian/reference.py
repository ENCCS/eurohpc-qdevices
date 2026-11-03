"""The stored numbers of the H2 curve, and their tables: PySCF's curves and the published values. Standard library only.

Lengths are in angstrom and energies in hartree, with the nuclei. `exact_chemistry.py` makes the curves.
"""

import re
from dataclasses import dataclass
from math import comb, prod
from typing import Final

from hydrogen import Curve, stored_numbers

KCAL: Final = 627.509474        # kcal/mol in one hartree: CODATA, with the thermochemical kilocalorie
NEAREST: Final = 8              # the published rows that one interpolation goes through
EQUILIBRIUM: Final = 0.7414
STRETCHED: Final = 3.0
SMALL, LARGE = "sto-3g", "cc-pvqz"
NAMES: Final = {"sto-3g": "STO-3G", "6-31g": "6-31G", "cc-pvdz": "cc-pVDZ", "cc-pvtz": "cc-pVTZ", "cc-pvqz": "cc-pVQZ"}


@dataclass(frozen=True, slots=True)
class Row:
    """One published value: its distance in bohr, its energy, and the accuracy stated in its last digits."""

    bohr: float
    energy: float
    stated: float

    @classmethod
    def of(cls, bohr: str, printed: str) -> "Row":
        """A row from its text, such as -1.0200566663605151(4); a row with no bracket states no accuracy."""
        found = re.fullmatch(r"(-?\d+\.(\d+))(?:\((\d+)\))?", printed)
        return cls(float(bohr), float(found[1]), int(found[3] or 0) * 10.0 ** -len(found[2]))


@dataclass(frozen=True, slots=True)
class Reference:
    """What the file holds: the curves of each basis, the published rows, and the published minimum."""

    lengths: tuple[float, ...]
    bohr: float
    bases: dict[str, dict]
    rows: tuple[Row, ...]
    minimum: Row

    @classmethod
    def load(cls) -> "Reference":
        """The numbers of reference_curve.json."""
        held = stored_numbers()
        pyscf, published = held["pyscf"], held["published"]
        return cls(tuple(pyscf["lengths_angstrom"]), pyscf["bohr_in_angstrom"], pyscf["bases"],
                   tuple(Row.of(*item) for item in published["table_iv_by_bohr"].items()),
                   Row.of(*next(iter(published["abstract_at_minimum"].items()))))

    def _curve(self, basis: str, method: str, length: float) -> float:
        return self.bases[basis][method][self.lengths.index(length)]

    def fci(self, basis: str, length: float) -> float:
        """Full configuration interaction: exact within the basis."""
        return self._curve(basis, "fci", length)

    def hartree_fock(self, basis: str, length: float) -> float:
        """Restricted Hartree-Fock."""
        return self._curve(basis, "restricted_hartree_fock", length)

    def published(self, length: float) -> float:
        """The published energy at a length, by our polynomial of E - 1/r through the nearest rows."""
        r = length / self.bohr
        near = sorted(self.rows, key=lambda row: abs(row.bohr - r))[:NEAREST]
        return 1 / r + sum((row.energy - 1 / row.bohr)
                           * prod((r - other.bohr) / (row.bohr - other.bohr) for other in near if other is not row)
                           for row in near)

    def points(self, low: float, high: float, every: float = 0.2) -> list[tuple[float, float]]:
        """The published rows between two lengths, as printed, at each multiple of `every` bohr, which holds 1.4."""
        lengths = ((row.bohr * self.bohr, row.energy) for row in self.rows if round(row.bohr / every, 6).is_integer())
        return [(length, energy) for length, energy in lengths if low <= length <= high]


def _above(energy: float, best: float) -> str:
    return f"{energy:>8.4f} {energy - best:>+8.4f} {(energy - best) * KCAL:>+7.1f}"


def _methods(reference: Reference, curve: Curve) -> tuple:
    return (("restricted Hartree-Fock, STO-3G", lambda r: reference.hartree_fock(SMALL, r)),
            ("exact in STO-3G: FCI", lambda r: reference.fci(SMALL, r)),
            (f"phase estimation in STO-3G, {curve.bits} bits", lambda r: curve.at(r).energy),
            ("restricted Hartree-Fock, cc-pVQZ", lambda r: reference.hartree_fock(LARGE, r)),
            ("FCI, cc-pVQZ", lambda r: reference.fci(LARGE, r)))


def methods(curve: Curve, lengths: tuple[float, float] = (EQUILIBRIUM, STRETCHED)) -> str:
    """Each method against the best published value at two lengths: its energy, and how far above, in two units."""
    reference = Reference.load()
    best = [reference.published(r) for r in lengths]
    head = f"{'':<37}" + "".join(f"{f'at {r} angstrom':<27}" for r in lengths)
    columns = f"{'method':<37}" + f"{'hartree':>8} {'above':>8} {'kcal/mol':>8}  " * 2
    rows = [f"{name:<37}" + "  ".join(_above(energy(r), b) + " " for r, b in zip(lengths, best, strict=True))
            for name, energy in _methods(reference, curve)]
    last = f"{'published, by interpolation':<37}" + "  ".join(f"{b:>8.4f} {'':>17}" for b in best)
    return "\n".join([head, columns, *rows, last])


def bases(length: float = EQUILIBRIUM) -> str:
    """Each basis: M spin orbitals, which are the qubits before any symmetry, the exact space, and the FCI error."""
    reference = Reference.load()
    rows = [f"{'':<27}FCI above the published value", f"{'':<27}{f'at {length} angstrom':<22}largest on the curve",
            f"{'basis':<8}{'M':>4}{'C(M, 2)':>9}{'':>6}{'hartree':>9}{'kcal/mol':>9}{'hartree':>13}{'kcal/mol':>9}"]
    for basis, name in NAMES.items():
        at = reference.fci(basis, length) - reference.published(length)
        worst = max(reference.fci(basis, r) - reference.published(r) for r in reference.lengths)
        qubits = reference.bases[basis]["spin_orbitals"]
        rows.append(f"{name:<8}{qubits:>4}{comb(qubits, 2):>9}{'':>6}{at:>9.5f}{at * KCAL:>9.2f}{worst:>13.5f}"
                    f"{worst * KCAL:>9.2f}")
    return "\n".join(rows)
