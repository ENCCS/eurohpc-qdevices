"""The two spins in QuTiP: the Hamiltonian, its levels, the exact evolution, the Trotter steps, and one chart.

Qubit 0 is the first factor of each tensor product. A key reads q[1] q[0], as the machine returns it.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import qutip as qt
from palette import BLUE, GREY, GRID, INK, ORANGE, TEAL
from trotter import COUPLING, FIELD, T

KEYS = ("00", "01", "10", "11")
COLOURS = {"00": BLUE, "01": TEAL, "10": GREY, "11": ORANGE}


def _two(a: qt.Qobj, b: qt.Qobj) -> qt.Qobj:
    return qt.tensor(a, b)


def zz() -> qt.Qobj:
    """Z0 Z1."""
    return _two(qt.sigmaz(), qt.sigmaz())


def x_both() -> qt.Qobj:
    """X0 + X1."""
    return _two(qt.sigmax(), qt.qeye(2)) + _two(qt.qeye(2), qt.sigmax())


def hamiltonian(field: float = FIELD, coupling: float = COUPLING) -> qt.Qobj:
    """H = -J Z0 Z1 - h (X0 + X1)."""
    return -coupling * zz() - field * x_both()


def start() -> qt.Qobj:
    """Both spins in |0>: the key 00."""
    return _two(qt.basis(2, 0), qt.basis(2, 0))


def projector(key: str) -> qt.Qobj:
    """The projector on one key; its right-hand character is q[0]."""
    state = _two(qt.basis(2, int(key[1])), qt.basis(2, int(key[0])))
    return state * state.dag()


def shares(state: qt.Qobj) -> dict:
    """The share of each key in a state."""
    return {key: float(qt.expect(projector(key), state)) for key in KEYS}


def exact(t: float = T, field: float = FIELD) -> dict:
    """The shares at t, by the propagator exp(-iHt): no Trotter error."""
    return shares((-1j * hamiltonian(field) * t).expm() * start())


def over_time(times: np.ndarray, field: float = FIELD) -> dict:
    """The share of each key at each time, by QuTiP's solver of the Schrodinger equation."""
    result = qt.sesolve(hamiltonian(field), start(), times, e_ops=[projector(key) for key in KEYS],
                        options={"atol": 1e-10, "rtol": 1e-8})
    return dict(zip(KEYS, result.expect, strict=True))


def step(dt: float, field: float = FIELD) -> qt.Qobj:
    """One first-order Trotter step: exp(-i dt ZZ term), then exp(-i dt X term), as Qrisp's text has them."""
    return (1j * field * dt * x_both()).expm() * (1j * COUPLING * dt * zz()).expm()


def product(steps: int, t: float = T, field: float = FIELD) -> qt.Qobj:
    """The N Trotter steps to the time t, as one 4 x 4 unitary."""
    return step(t / steps, field) ** steps


def trotter(steps: int, t: float = T, field: float = FIELD) -> dict:
    """The shares after N Trotter steps to the time t."""
    return shares(product(steps, t, field) * start())


def error(steps: int, t: float = T, field: float = FIELD) -> float:
    """The largest error on any state: the operator norm of the N steps less exp(-iHt)."""
    exact_u = (-1j * hamiltonian(field) * t).expm()
    return float(np.linalg.norm((product(steps, t, field) - exact_u).full(), 2))


def _rz(angle: float) -> qt.Qobj:
    return (-0.5j * angle * qt.sigmaz()).expm()


def gates_against_exponentials(angle: float = 0.7) -> tuple:
    """The largest difference of CX, RZ, CX from exp(-i a ZZ/2), and of H, RZ, H from exp(-i a X/2)."""
    cx = qt.Qobj(np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]]), dims=[[2, 2], [2, 2]])
    hadamard = (qt.sigmax() + qt.sigmaz()) / np.sqrt(2)
    zz_gates = cx * _two(qt.qeye(2), _rz(angle)) * cx
    x_gates = hadamard * _rz(angle) * hadamard
    return (float(np.abs((zz_gates - (-0.5j * angle * zz()).expm()).full()).max()),
            float(np.abs((x_gates - (-0.5j * angle * qt.sigmax()).expm()).full()).max()))


def cx_needed(unitary: qt.Qobj) -> int:
    """The fewest CX that make a two-qubit unitary with one-qubit gates: the test of Shende, Bullock and Markov."""
    u = unitary.full()
    u = u / complex(np.linalg.det(u)) ** 0.25
    yy = np.kron(qt.sigmay().full(), qt.sigmay().full())
    poly = np.poly(u @ yy @ u.T @ yy)                    # the characteristic polynomial of gamma(u)
    if np.allclose(poly, [1, -4, 6, -4, 1], atol=1e-9) or np.allclose(poly, [1, 4, 6, 4, 1], atol=1e-9):
        return 0
    if np.allclose(poly, [1, 0, 2, 0, 1], atol=1e-9):
        return 1
    return 2 if np.allclose(poly.imag, 0, atol=1e-9) else 3


def chart(times: np.ndarray, curves: dict, mark: float = T):
    """The share of each key against the time, with the time of the jobs marked."""
    fig, ax = plt.subplots(figsize=(6.4, 3.4), dpi=120)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for key in KEYS:
        ax.plot(times, curves[key], color=COLOURS[key], linewidth=2, linestyle="--" if key == "10" else "-",
                label=key + (": the same as 01" if key == "10" else ""))
    ax.axvline(mark, color=INK, linewidth=0.8)
    ax.text(mark, 1.04, " the jobs: t = 2π/2.6", color=INK, fontsize=9, va="bottom")
    ax.set_xlabel("time t, in units of ħ/J", color=INK)
    ax.set_ylabel("share of the shots", color=INK)
    ax.set_ylim(-0.02, 1.12)
    ax.tick_params(colors=INK)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.08), ncols=4, labelcolor=INK)
    fig.tight_layout()
    return fig
