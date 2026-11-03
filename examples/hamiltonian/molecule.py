"""H2 in STO-3G from first principles, and ideal phase estimation of it. NumPy and the standard library only.

Lengths are in angstrom and energies in hartree. A test holds the results against PySCF at every stored length.
"""

from dataclasses import dataclass
from functools import cached_property
from math import pi, sqrt
from typing import Final, NamedTuple

import numpy as np
from hydrogen import energy_of, lowest_strong_peak
from integrals import Integrals

BOHR: Final = 0.52917721092                     # in angstrom: the value PySCF uses
GOLDEN: Final = (sqrt(5) - 1) / 2


class Terms(NamedTuple):
    """The coefficients of the two-qubit Hamiltonian, for the electrons alone, in the form of Qrisp's page."""

    identity: float
    z0: float
    z1: float
    z0z1: float
    x0x1: float


# Qrisp's page, which names no length; these digits match 0.735 angstrom
PAGE: Final = Terms(-1.05237325, 0.39793742, -0.39793742, -0.0112801, 0.1809312)


@dataclass(frozen=True)
class Molecule:
    """H2 at a bond length. Symmetry fixes the two orbitals, so restricted Hartree-Fock needs no iteration."""

    length: float

    @cached_property
    def _in_orbitals(self) -> tuple[np.ndarray, np.ndarray]:
        """The integrals h and (ij|kl) in the bonding and antibonding orbitals, g and u."""
        held = Integrals(self.length / BOHR)
        s = held.overlap()[0, 1]
        c = np.array([[1, 1], [1, -1]]) / np.sqrt([2 * (1 + s), 2 * (1 - s)])
        return c.T @ held.core() @ c, np.einsum("pqrs,pi,qj,rk,sl->ijkl", held.repulsion(), c, c, c, c)

    @property
    def nuclear(self) -> float:
        """The repulsion of the nuclei."""
        return BOHR / self.length

    @cached_property
    def block(self) -> np.ndarray:
        """The Hamiltonian of the electrons on the states g^2 and u^2: all that the start reaches."""
        h, eri = self._in_orbitals
        return np.array([[2 * h[0, 0] + eri[0, 0, 0, 0], eri[0, 1, 0, 1]],
                         [eri[0, 1, 0, 1], 2 * h[1, 1] + eri[1, 1, 1, 1]]])

    @property
    def hartree_fock(self) -> float:
        """The restricted Hartree-Fock energy, with the nuclei: the state g^2."""
        return float(self.block[0, 0] + self.nuclear)

    @property
    def exact(self) -> float:
        """The exact energy in this basis, with the nuclei: full configuration interaction."""
        return float(np.linalg.eigvalsh(self.block)[0] + self.nuclear)

    @property
    def overlap(self) -> float:
        """The squared overlap of the restricted Hartree-Fock state with the ground state."""
        return float(np.linalg.eigh(self.block)[1][0, 0] ** 2)

    @cached_property
    def terms(self) -> Terms:
        """The two-qubit form: the x(qv[0]) start, q[0] = 1 and q[1] = 0, is g^2, and q[0] = 0, q[1] = 1 is u^2."""
        h, eri = self._in_orbitals
        cross, same = eri[0, 0, 1, 1] / 2, (eri[0, 0, 0, 0] + eri[1, 1, 1, 1]) / 4
        z = (h[1, 1] - h[0, 0]) / 2 + (eri[1, 1, 1, 1] - eri[0, 0, 0, 0]) / 4
        return Terms(*map(float, (h[0, 0] + h[1, 1] + same + cross, z, -z, cross - same, eri[0, 1, 0, 1])))

    def _formula(self, steps: int) -> tuple[np.ndarray, np.ndarray]:
        """The levels and vectors of first-order steps: the Z terms and the X0 X1 term, each for a time 1 / steps."""
        mix = self.block[0, 1] / steps
        turn = np.array([[np.cos(mix), -1j * np.sin(mix)], [-1j * np.sin(mix), np.cos(mix)]])
        values, vectors = np.linalg.eig(np.diag(np.exp(-1j * np.diag(self.block) / steps)) @ turn)
        return -np.angle(values) * steps, vectors

    def levels(self, steps: int | None = None) -> list[tuple[float, float]]:
        """Each level the start reaches, with no nuclei, and its share of the start; with steps, of the formula."""
        values, vectors = self._formula(steps) if steps else np.linalg.eigh(self.block)
        return sorted((float(e), float(abs(v) ** 2)) for e, v in zip(values, vectors[0], strict=True))


def atom_energy() -> float:
    """The energy of one hydrogen atom in STO-3G: with one electron, the basis is all that limits it."""
    return sum(pair.kinetic() + pair.attraction(0.0) for pair in Integrals(0.0).pairs[0, 0])


def minimum(low: float = 0.6, high: float = 0.9) -> Molecule:
    """The molecule at the minimum of the exact curve in STO-3G, by golden-section search."""
    while high - low > 1e-7:
        left, right = high - GOLDEN * (high - low), low + GOLDEN * (high - low)
        low, high = (low, right) if Molecule(left).exact < Molecule(right).exact else (left, high)
    return Molecule((low + high) / 2)


def difference_from_page() -> Terms:
    """How far the terms at 0.735 angstrom lie from the numbers that Qrisp's page prints."""
    return Terms(*(mine - page for mine, page in zip(Molecule(0.735).terms, PAGE, strict=True)))


@dataclass(frozen=True)
class PhaseEstimation:
    """The closed form of phase estimation at t = 1 from the restricted Hartree-Fock start: of H, or of the formula."""

    molecule: Molecule
    bits: int
    steps: int | None = None

    def shares(self) -> dict[float, float]:
        """The share of each phase m / 2^bits, which stands for the energy E = -2 pi m / 2^bits, with no nuclei."""
        size = 2 ** self.bits
        energies, weights = zip(*self.molecule.levels(self.steps), strict=True)
        apart = (np.arange(size) / size)[:, None] - (-np.array(energies) / (2 * pi)) % 1
        return dict(zip(np.arange(size) / size, (np.sinc(size * apart) / np.sinc(apart)) ** 2 @ np.array(weights),
                        strict=True))

    def top(self) -> float:
        """The energy of the top reading, with the nuclei: at a stretched bond this can be the wrong level."""
        found = self.shares()
        return float(energy_of(max(found, key=found.get)) + self.molecule.nuclear)

    def reading(self) -> float:
        """The energy of the lowest strong peak, with the nuclei."""
        return float(energy_of(lowest_strong_peak(self.shares(), self.bits)) + self.molecule.nuclear)
