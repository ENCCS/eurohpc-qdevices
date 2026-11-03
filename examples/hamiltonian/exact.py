"""The exact shares by QuTiP against the closed form in chain.py. QuTiP stays out of every lock: use `pixi exec`."""

from typing import Final

import qutip as qt
from chain import BONDS, SPINS, T, closed_form

TIMES: Final = {"0": 0.0, "T/4": T / 4, "T/2": T / 2, "3T/4": 3 * T / 4, "T": T, "2T": 2 * T}
KEYS: Final = ("001", "010", "100")


def bond_term(a: int, b: int) -> qt.Qobj:
    """(XX + YY) / 2 on one bond; the first factor of a product is q[0]."""
    def on(pauli: qt.Qobj) -> qt.Qobj:
        return qt.tensor([pauli if q in (a, b) else qt.qeye(2) for q in range(SPINS)])
    return 0.5 * (on(qt.sigmax()) + on(qt.sigmay()))


def excited(site: int) -> qt.Qobj:
    """The state with the excitation on one site: basis(2, 1) has Z = -1, so it reads 1."""
    return qt.tensor([qt.basis(2, 1 if q == site else 0) for q in range(SPINS)])


class Solver:
    """The chain in QuTiP, from the excitation on q[0]."""

    def __init__(self) -> None:
        self.ham = sum(bond_term(a, b) for a, b in BONDS)
        self.start = excited(0)

    def shares(self, t: float) -> list[float]:
        """The share of the key of each site at the time t."""
        final = qt.sesolve(self.ham, self.start, [0.0, t + 1e-12], options={"atol": 1e-12, "rtol": 1e-12}).states[-1]
        return [abs(excited(site).overlap(final)) ** 2 for site in range(SPINS)]


def main() -> int:
    """Print the two sets of shares; 1 when they differ."""
    solver, worst = Solver(), 0.0
    print(f"{'t':>5} {'sesolve 001, 010, 100':>26} {'closed form':>26}")
    for name, t in TIMES.items():
        solved, closed = solver.shares(t), [closed_form(t)[key] for key in KEYS]
        worst = max(worst, *(abs(a - b) for a, b in zip(solved, closed, strict=True)))
        print(f"{name:>5} " + " ".join(f"{share:8.4f}" for share in (*solved, *closed)))
    print(f"largest difference: {worst:.1e}")
    return 0 if worst < 1e-6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
