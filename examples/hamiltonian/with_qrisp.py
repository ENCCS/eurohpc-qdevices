"""The tutorial's uses of Qrisp: the chain in one line, and hydrogen inside phase estimation. It needs Qrisp.

To make the stored run of the curve again and keep it in reference_curve.json, from this folder:

    pixi run --manifest-path ../qrisp/pixi.toml python with_qrisp.py
"""

from contextlib import redirect_stderr, redirect_stdout
from importlib.metadata import version
from io import StringIO
from typing import Final

import numpy as np
from chain import SPINS
from hydrogen import Curve, Estimates, Point, Size, energy_of, lowest_strong_peak
from molecule import PAGE, Molecule, Terms
from qrisp import QPE, QuantumVariable
from qrisp.core import x
from qrisp.operators import X, Y, Z

STEPS: Final = 3                    # first-order steps per unit time
BITS: Final = 8                     # a grid step of 0.025 hartree, and seconds at each length
LENGTHS: Final = (0.5, 0.7414, 1.1, 1.4, 1.8, 2.6, 3.0, 4.0)


def chain_by_qrisp(t: float, steps: int) -> QuantumVariable:
    """Qrisp's one line for the Hamiltonian of the chain, from the excitation on q[0]."""
    ham = 0.5 * sum(X(k) * X(k + 1) + Y(k) * Y(k + 1) for k in range(SPINS - 1))
    qv = QuantumVariable(SPINS)
    x(qv[0])
    ham.trotterization(order=2, method="commuting")(qv, t=t, steps=steps)
    return qv


def measured(variable) -> dict:
    """The shares of a variable on Qrisp's own emulator, with no progress bar."""
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return variable.get_measurement()


def operator(terms: Terms):
    """The two-qubit Hamiltonian from its coefficients."""
    return (terms.identity + terms.z0 * Z(0) + terms.z1 * Z(1) + terms.z0z1 * Z(0) * Z(1)
            + terms.x0x1 * X(0) * X(1))


def h2():
    """The two-qubit Hamiltonian of the hydrogen molecule on Qrisp's ground-state page."""
    return operator(PAGE)


def phase_register(ham, bits: int):
    """Phase estimation of a Hamiltonian from its restricted Hartree-Fock state, by the first-order formula."""
    qv = QuantumVariable(2)
    x(qv[0])
    return QPE(qv, ham.trotterization(), precision=bits, kwargs={"steps": STEPS}, iter_spec=True)


def size_of(phase) -> tuple[int, int]:
    """The qubits and the two-qubit gates of a register's circuit."""
    circuit = phase.qs.compile().transpile()
    return circuit.num_qubits(), sum(i.op.name in ("cx", "cz") for i in circuit.data)


def estimate(bits: int) -> tuple[Size, dict]:
    """Phase estimation of H2 with the numbers of the page, at 3 steps per unit time; the shares of phases."""
    phase = phase_register(h2(), bits)
    found = measured(phase)
    return Size(bits, *size_of(phase), max(found, key=found.get)), found


def hydrogen(bits: tuple[int, ...] = (3, 4, 5, 6)) -> Estimates:
    """Phase estimation of H2 at each size, and the share of each energy at the largest."""
    done = [estimate(n) for n in bits]
    energies = {energy_of(phase): share for phase, share in done[-1][1].items()}
    return Estimates(float(np.linalg.eigvalsh(h2().to_array())[0]), tuple(size for size, _ in done), energies)


def shares_at(length: float, bits: int) -> dict:
    """The shares of phases at a bond length, in hartree of the electrons alone."""
    return measured(phase_register(operator(Molecule(length).terms), bits))


def point(length: float, bits: int) -> Point:
    """One bond length: read by the rule, and by the top reading."""
    molecule, found = Molecule(length), shares_at(length, bits)
    phase, top = lowest_strong_peak(found, bits), max(found, key=found.get)
    return Point(length, *(round(v, 8) for v in (molecule.nuclear, molecule.exact, molecule.overlap)), phase,
                 found[phase], top, found[top])


def curve(lengths: tuple[float, ...] = LENGTHS, bits: int = BITS) -> Curve:
    """Phase estimation at each bond length. The gates are the same at each, so they are counted once."""
    return Curve(bits, STEPS, *size_of(phase_register(h2(), bits)), version("qrisp"),
                 tuple(point(length, bits) for length in lengths))


if __name__ == "__main__":
    curve().store()
