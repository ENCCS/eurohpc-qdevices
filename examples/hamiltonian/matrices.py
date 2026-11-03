"""The chain as matrices, for the tutorial: exact evolution, product formulas, Jordan-Wigner. NumPy and SciPy only.

A word or a key reads q[n-1] ... q[0], so the index of a vector, in binary, is the key the machine returns.
"""

from dataclasses import dataclass
from functools import reduce
from typing import Final

import numpy as np
from scipy.linalg import expm

PAULI: Final = {"I": np.eye(2, dtype=complex), "X": np.array([[0, 1], [1, 0]], dtype=complex),
                "Y": np.array([[0, -1j], [1j, 0]], dtype=complex), "Z": np.array([[1, 0], [0, -1]], dtype=complex)}
LOWER: Final = 0.5 * (PAULI["X"] + 1j * PAULI["Y"])     # |1> to |0>, the qubit reads 1 when the orbital is full
CX: Final = np.array([[1, 0, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0], [0, 1, 0, 0]], dtype=complex)   # q[0] controls q[1]


def pauli(word: str) -> np.ndarray:
    """The matrix of a Pauli word such as "IXX": X on q[1] and on q[0]."""
    return reduce(np.kron, (PAULI[c] for c in word))


A: Final = 0.5 * (pauli("IXX") + pauli("IYY"))
B: Final = 0.5 * (pauli("XXI") + pauli("YYI"))
H: Final = A + B


def start() -> np.ndarray:
    """The state of the key 001: the excitation on q[0]."""
    state = np.zeros(8, dtype=complex)
    state[1] = 1
    return state


def exact(t: float) -> np.ndarray:
    """exp(-iHt)."""
    return expm(-1j * H * t)


def shares(state: np.ndarray) -> dict[str, float]:
    """The share of each key that holds one."""
    n = int(np.log2(len(state)))
    return {f"{i:0{n}b}": float(abs(v) ** 2) for i, v in enumerate(state) if abs(v) ** 2 > 1e-9}


def bond(theta: float) -> np.ndarray:
    """The gates of one bond on two qubits: Rx(pi/2) on both, CX, Rx and Rz by theta, CX, Rx(-pi/2) on both."""
    rx = lambda angle: expm(-0.5j * angle * PAULI["X"])     # noqa: E731
    turn = np.kron(rx(np.pi / 2), rx(np.pi / 2))
    return turn.conj().T @ CX @ np.kron(expm(-0.5j * theta * PAULI["Z"]), rx(theta)) @ CX @ turn


@dataclass(frozen=True, slots=True)
class Formula:
    """A product formula for exp(-iHt): N steps of order 1 or 2, in which A acts first, as in the text of a job."""

    t: float
    steps: int
    order: int = 2

    def matrix(self) -> np.ndarray:
        """The matrix of all the steps."""
        dt = self.t / self.steps
        half = expm(-1j * A * dt / 2)
        step = expm(-1j * B * dt) @ expm(-1j * A * dt) if self.order == 1 else half @ expm(-1j * B * dt) @ half
        return np.linalg.matrix_power(step, self.steps)

    def error(self) -> float:
        """The largest error on any state: the operator norm of the difference from exp(-iHt)."""
        return float(np.linalg.norm(self.matrix() - exact(self.t), 2))


@dataclass(frozen=True, slots=True)
class JordanWigner:
    """Some orbitals on as many qubits: a qubit reads 1 when its orbital is full."""

    orbitals: int

    def annihilate(self, orbital: int) -> np.ndarray:
        """The operator a that empties an orbital, with a Z on each orbital below it."""
        parts = (PAULI["I"] if q > orbital else LOWER if q == orbital else PAULI["Z"]
                 for q in reversed(range(self.orbitals)))
        return reduce(np.kron, parts)

    def hop(self, p: int, q: int) -> np.ndarray:
        """An electron moving between two orbitals, either way: a+_p a_q + a+_q a_p."""
        a_p, a_q = self.annihilate(p), self.annihilate(q)
        return a_p.conj().T @ a_q + a_q.conj().T @ a_p
