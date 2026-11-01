"""Small Qrisp programs, each with the outcome a perfect machine would give, in Qrisp's labels."""

from collections.abc import Callable
from dataclasses import dataclass
from math import pi
from typing import Final

import networkx as nx
import numpy as np
from qrisp import QFT, PGate, QuantumBool, QuantumCircuit, QuantumFloat, QuantumModulus, QuantumVariable, auto_uncompute
from qrisp.core import cx, h, mcp, p, rx, rz, rzz
from qrisp.environments import conjugate, control, invert
from qrisp.grover import grovers_alg
from qrisp.operators import X, Z
from qrisp.qite import QITE
from sympy import Symbol

__all__ = ["PROGRAMS", "Program"]


@dataclass(frozen=True, slots=True)
class Program:
    """One example: its job name, what it does, what a perfect machine would give, how to build it, its shots."""

    name: str
    what: str
    ideal: str
    build: Callable[[], QuantumVariable | QuantumCircuit]
    shots: int = 100

    def circuit(self) -> QuantumCircuit:
        """The compiled circuit of the program, every qubit measured in order, in qelib1.inc gates."""
        made = self.build()
        qc = made if isinstance(made, QuantumCircuit) else made.qs.compile()
        qc.measure(qc.qubits)
        return qc.transpile()


def bell() -> QuantumVariable:
    """A Bell pair on two qubits."""
    qv = QuantumVariable(2)
    h(qv[0])
    cx(qv[0], qv[1])
    return qv


def ghz(n: int = 3) -> QuantumVariable:
    """A GHZ state on n qubits."""
    qv = QuantumVariable(n)
    h(qv[0])
    for i in range(1, n):
        cx(qv[0], qv[i])
    return qv


def qft3(k: int = 5) -> QuantumFloat:
    """The Fourier state of k on three qubits, then the inverse QFT, which gives k back."""
    qf = QuantumFloat(3)
    h(qf)
    for i in range(3):
        p(2 * pi * k * 2**i / 8, qf[i])
    QFT(qf, inv=True)
    return qf


# The eight below follow pages of the Qrisp documentation, under
# https://github.com/eclipse-qrisp/Qrisp/blob/main/documentation/source/ ; a page's loop of angles is one fixed choice.
GRAPH: Final = nx.Graph([(0, 3), (0, 4), (1, 3), (1, 4), (2, 3), (2, 4)])


def abstract_parameter() -> QuantumCircuit:
    """reference/Examples/AbstractParameter.rst: H, then a phase gate controlled on 00, with phi bound to pi/2."""
    phi = Symbol("phi")
    qc = QuantumCircuit(3)
    qc.h(-1)
    qc.append(PGate(phi).control(2, ctrl_state="00"), qc.qubits)
    return qc.bind_parameters({phi: pi / 2})


def qaoa_maxcut(g: float = 0.3, b: float = 1.0999999999999999) -> QuantumVariable:
    """general/tutorial/QAOAtutorial/MaxCut.ipynb: one QAOA layer, the angles of a coarse grid on the simulator."""
    qv = QuantumVariable(5)
    h(qv)
    for i, j in GRAPH.edges():
        cx(qv[i], qv[j])
        rz(2 * g, qv[j])
        cx(qv[i], qv[j])
    for i in range(5):
        rx(2 * b, qv[i])
    return qv


def tutorial_qpe() -> QuantumVariable:
    """general/tutorial/tutorial.ipynb: QPE of two phase gates on psi, with three bits of precision."""
    psi = QuantumVariable(2)
    h(psi)
    res = QuantumFloat(3, -3)
    h(res)
    for i in range(3):
        with control(res[i]):
            for _ in range(2**i):
                p(0.5 * 2 * np.pi, psi[0])
                p(0.125 * 2 * np.pi, psi[1])
    QFT(res, inv=True)
    return psi


def qubo(g: float = 2.6, b: float = 0.5) -> QuantumVariable:
    """general/tutorial/QAOAtutorial/QUBO.ipynb: one QAOA layer for its matrix, the angles of a coarse grid."""
    q = np.array([[-17, 10, 10, 10, 0, 20], [10, -18, 10, 10, 10, 20], [10, 10, -29, 10, 20, 20],
                  [10, 10, 10, -19, 10, 10], [0, 10, 20, 10, -17, 10], [20, 20, 20, 10, 10, -28]])
    g = g / np.sqrt(np.linalg.norm(q))
    qv = QuantumVariable(6)
    h(qv)
    for i in range(6):
        rz(-g / 2 * (sum(q[i]) + sum(q[:, i])), qv[i])
        for j in range(6):
            if i != j and q[i][j] != 0:
                rzz(g / 2 * q[i][j], qv[i], qv[j])
    for i in range(6):
        rx(2 * b, qv[i])
    return qv


@auto_uncompute
def _parity_oracle(qv, phase):
    flag = QuantumBool()
    cx(qv[0], flag)
    cx(qv[-1], flag)
    p(phase, flag)


def _prepare(qv):
    with invert():
        grovers_alg(qv, _parity_oracle, exact=True, winner_state_amount=2 ** (len(qv) - 1))


def constrained_mixer() -> QuantumVariable:
    """general/tutorial/QAOAtutorial/ConstrainedMixers.ipynb: the mixer on the allowed state 011, beta = pi."""
    qv = QuantumVariable(3)
    qv[:] = "011"
    with conjugate(_prepare)(qv):
        mcp(np.pi, qv, ctrl_state=0)
    return qv


def qite1(s: float = 0.1388888888888889) -> QuantumVariable:
    """reference/Examples/MaxCutQITE.rst: one QITE step of MaxCut, its evolution time fixed."""
    def exp_h(qv, gamma):
        for i, j in GRAPH.edges():
            rzz(2 * gamma, qv[i], qv[j])
    qv = QuantumVariable(5)
    QITE(qv, h, exp_h, [s], 1)
    return qv


def ising(t: float = 1.0) -> QuantumVariable:
    """reference/Examples/IsingModel.rst: five Trotter steps of a chain of six spins, to the time t."""
    ham = sum(-1.0 * Z(k) * Z(k + 1) for k in range(5)) + sum(1.0 * X(k) for k in range(6))
    qv = QuantumVariable(6)
    ham.trotterization()(qv, t=t, steps=5)
    return qv


def shor13() -> QuantumModulus:
    """general/tutorial/Shor.ipynb: 8 + 8 modulo 13."""
    qg = QuantumModulus(13)
    qg[:] = 8
    qg += 8
    return qg


PROGRAMS: Final = (
    Program("BELL", "a Bell pair: H, CX", "00 and 11, about half each", bell),
    Program("GHZ3", "a three-qubit GHZ state: H, two CX", "000 and 111, about half each", ghz),
    Program("QFT3", "the Fourier state of 5 on three qubits, then the inverse QFT",
            "101 every time, the number 5", qft3),
    Program("ABSTRACT_PARAMETER", "H, then a phase gate controlled on 00 (phi = pi/2)",
            "000 and 100, about half each (a circuit's label: q[2] leftmost)", abstract_parameter, 1000),
    Program("QAOA_MAXCUT", "one QAOA layer of MaxCut on five nodes", "11100 and 00011, about 0.2 each",
            qaoa_maxcut, 1000),
    Program("TUTORIAL_QPE", "QPE of two phase gates, three bits", "(psi, phase) (00, 0), (10, 0.5), (01, 0.125), "
            "(11, 0.625), a quarter each", tutorial_qpe, 1000),
    Program("QUBO", "one QAOA layer of a six-variable QUBO", "001001 most often, about 0.2", qubo, 1000),
    Program("CONSTRAINED_MIXER", "a constrained QAOA mixer on 011", "100, 110, 001 and 011, a quarter each",
            constrained_mixer, 1000),
    Program("QITE1", "one QITE step of MaxCut on five nodes", "11100 and 00011 most often, about 0.05 each",
            qite1, 1000),
    Program("ISING", "five Trotter steps of a six-spin Ising chain", "000000 most often, about 0.13", ising, 1000),
    Program("SHOR13", "8 + 8 modulo 13", "3 every time", shor13, 1000),
)
