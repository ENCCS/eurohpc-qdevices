"""The integrals of H2 in STO-3G from first principles: one contracted s function on each nucleus. NumPy only.

Distances are in bohr and energies in hartree.
"""

from dataclasses import dataclass
from itertools import product
from math import erf, exp, pi, sqrt
from typing import Final

import numpy as np

EXPONENTS: Final = (3.42525091, 0.62391373, 0.16885540)         # STO-3G for hydrogen, as PySCF holds it
WEIGHTS: Final = (0.15432897, 0.53532814, 0.44463454)
_PRIMITIVES: Final = [(a, w * (2 * a / pi) ** 0.75) for a, w in zip(EXPONENTS, WEIGHTS, strict=True)]
_NORM: Final = sum(wa * wb * (pi / (a + b)) ** 1.5 for (a, wa), (b, wb) in product(_PRIMITIVES, repeat=2))
CONTRACTION: Final = tuple((a, w / sqrt(_NORM)) for a, w in _PRIMITIVES)     # norm 1 for the whole function


def boys(x: float) -> float:
    """The Boys function of order 0: the integral of exp(-x t^2) for t from 0 to 1."""
    return 1 - x / 3 if x < 1e-12 else 0.5 * sqrt(pi / x) * erf(sqrt(x))


@dataclass(frozen=True, slots=True)
class Pair:
    """The product of two s Gaussians on the axis, which is one Gaussian: its exponent, place and weight."""

    exponent: float
    place: float
    weight: float
    reduced: float      # a b / (a + b)
    apart: float        # the squared distance between the two centres

    @classmethod
    def of(cls, a: tuple[float, float], b: tuple[float, float], at_a: float, at_b: float) -> "Pair":
        """The product of two primitives (exponent, weight) at two places on the axis."""
        exponent, reduced, apart = a[0] + b[0], a[0] * b[0] / (a[0] + b[0]), (at_a - at_b) ** 2
        place = (a[0] * at_a + b[0] * at_b) / exponent
        return cls(exponent, place, a[1] * b[1] * exp(-reduced * apart), reduced, apart)

    def overlap(self) -> float:
        """Its integral over all space."""
        return self.weight * (pi / self.exponent) ** 1.5

    def kinetic(self) -> float:
        """The kinetic energy between the two primitives."""
        return self.overlap() * self.reduced * (3 - 2 * self.reduced * self.apart)

    def attraction(self, nucleus: float) -> float:
        """The attraction to a nucleus of charge 1 at a place on the axis."""
        return -self.weight * 2 * pi / self.exponent * boys(self.exponent * (self.place - nucleus) ** 2)

    def repulsion(self, other: "Pair") -> float:
        """The repulsion of this charge cloud and another."""
        p, q = self.exponent, other.exponent
        return (self.weight * other.weight * 2 * pi ** 2.5 / (p * q * sqrt(p + q))
                * boys(p * q / (p + q) * (self.place - other.place) ** 2))


class Integrals:
    """The integrals of two contracted s functions, one on each nucleus, a distance in bohr apart."""

    def __init__(self, distance: float) -> None:
        self.nuclei = (0.0, distance)
        self.pairs = {(i, j): [Pair.of(a, b, self.nuclei[i], self.nuclei[j]) for a, b in product(CONTRACTION, repeat=2)]
                      for i, j in product(range(2), repeat=2)}

    def _one(self, value) -> np.ndarray:
        return np.array([[sum(map(value, self.pairs[i, j])) for j in range(2)] for i in range(2)])

    def overlap(self) -> np.ndarray:
        """S: the overlap of the functions."""
        return self._one(Pair.overlap)

    def core(self) -> np.ndarray:
        """h: the kinetic energy and the attraction to both nuclei."""
        return self._one(lambda pair: pair.kinetic() + sum(pair.attraction(n) for n in self.nuclei))

    def repulsion(self) -> np.ndarray:
        """(ij|kl): the repulsion of two electrons, in chemists' order."""
        held = np.zeros((2, 2, 2, 2))
        for i, j, k, m in product(range(2), repeat=4):
            held[i, j, k, m] = sum(a.repulsion(b) for a, b in product(self.pairs[i, j], self.pairs[k, m]))
        return held
