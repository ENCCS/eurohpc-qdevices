"""One excitation on a chain of three spins: the model, its closed form, and Trotter steps as a text. No package."""

from dataclasses import dataclass
from math import cos, pi, sin, sqrt
from typing import Final

HEADER: Final = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
SPINS: Final = 3
BONDS: Final = ((0, 1), (1, 2))
T: Final = pi / sqrt(2)         # the excitation of q[0] arrives in full at q[2]


def closed_form(t: float) -> dict[str, float]:
    """The share of each key at the time t, for the excitation on q[0] at t = 0; a key reads q[2] q[1] q[0]."""
    return {"001": cos(t / sqrt(2)) ** 4, "010": sin(sqrt(2) * t) ** 2 / 2, "100": sin(t / sqrt(2)) ** 4}


def amplitudes(t: float) -> dict[str, complex]:
    """The amplitude of each key at the time t: unlike the shares, these show the sign of the time."""
    return {"001": complex(cos(t / sqrt(2)) ** 2), "010": -1j * sin(sqrt(2) * t) / sqrt(2),
            "100": complex(-sin(t / sqrt(2)) ** 2)}


def _lines(*body: str, excited: bool = True) -> str:
    register = [f"qreg q[{SPINS}];", f"creg c[{SPINS}];", *(["x q[0];"] if excited else [])]
    measures = [f"measure q[{q}] -> c[{q}];" for q in range(SPINS)]
    return HEADER + "\n".join([*register, *body, *measures]) + "\n"


def _bond(a: int, b: int, dt: float) -> list[str]:
    """exp(-i dt/2 (XX+YY)) on a bond, between the Rx(pi/2) layers of the whole register: 2 CX."""
    return [f"cx q[{a}],q[{b}];", f"rx({dt!r}) q[{a}];", f"rz({dt!r}) q[{b}];", f"cx q[{a}],q[{b}];"]


@dataclass(frozen=True, slots=True)
class Steps:
    """Trotter steps to the time t. Order 1: first bond, second bond. Order 2: half of the first, the second, half."""

    t: float
    steps: int
    order: int = 2
    excited: bool = True

    @property
    def layers(self) -> list[tuple[tuple[int, int], float]]:
        """Each bond in turn, with its time; at order 2, two half steps of the first bond run together."""
        first, second = BONDS
        dt = self.t / self.steps
        if self.order == 1:
            return [(bond, dt) for _ in range(self.steps) for bond in BONDS]
        whole = [(second, dt), (first, dt)] * self.steps
        return [(first, dt / 2), *whole[:-1], (first, dt / 2)]

    def text(self) -> str:
        """The steps as an OpenQASM 2 text, every qubit measured in order."""
        turn = [f"rx({pi / 2!r}) q[{q}];" for q in range(SPINS)]
        back = [f"rx({-pi / 2!r}) q[{q}];" for q in range(SPINS)]
        body = [line for (a, b), dt in self.layers for line in _bond(a, b, dt)]
        return _lines(*turn, *body, *back, excited=self.excited)


def control() -> str:
    """The excitation alone: the start key, so a reversed reading shows."""
    return _lines()
