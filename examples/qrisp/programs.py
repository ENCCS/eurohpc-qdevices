"""Small Qrisp programs, each with the outcome a perfect machine would give, in Qrisp's labels."""

import os
import platform
from collections.abc import Callable
from dataclasses import dataclass
from math import pi
from typing import Final

# NumPy's AVX-512 code puts some angles of Qrisp one bit apart; without it every x86 machine writes the same text.
if platform.machine().lower() in ("x86_64", "amd64"):
    os.environ.setdefault("NPY_DISABLE_CPU_FEATURES", "X86_V4 AVX512_ICL AVX512_SPR")
from pages import abstract_parameter, constrained_mixer, ising, qaoa_maxcut, qite1, qubo, shor13, tutorial_qpe
from qrisp import QFT, QuantumBool, QuantumCircuit, QuantumFloat, QuantumString, QuantumVariable
from qrisp.core import cx, h, p, x
from qrisp.grover import grovers_alg, tag_state
from qrisp.operators import X, Z

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


def bv4(secret: str = "1011") -> QuantumVariable:
    """Bernstein-Vazirani: one query of the oracle finds the hidden string."""
    qv = QuantumVariable(len(secret))
    flag = QuantumBool()
    x(flag)
    h(flag)
    h(qv)
    for i, bit in enumerate(secret):
        if bit == "1":
            cx(qv[i], flag)
    h(qv)
    h(flag)
    x(flag)
    return qv


def add_const(a: int = 3, b: int = 3) -> QuantumFloat:
    """Qrisp's arithmetic on three bits: a + b, with no modulus."""
    qf = QuantumFloat(3)
    qf[:] = a
    qf += b
    return qf


def grover3(winner: int = 6) -> QuantumFloat:
    """reference/Examples/ExactGrover.rst, cut to three qubits and one winner: one sharp answer."""
    def oracle(qf, phase=pi):
        tag_state({qf: winner}, phase=phase)
    qf = QuantumFloat(3)
    grovers_alg(qf, oracle, exact=True, winner_state_amount=1)
    return qf


def hello(word: str = "hello") -> QuantumString:
    """reference/Examples/HelloWorld.rst, cut to one word: five bits a letter, and no two-qubit gate."""
    q_str = QuantumString(size=len(word))
    q_str[:] = word
    return q_str


def ising2(t: float = 2 * pi / 2.6, steps: int = 5) -> QuantumVariable:
    """Two spins of the Ising model in a field, J = 1, field 1.2, first order, by Qrisp's trotterization."""
    ham = -1.0 * Z(0) * Z(1) - 1.2 * (X(0) + X(1))
    qv = QuantumVariable(2)
    ham.trotterization()(qv, t=t, steps=steps)
    return qv


PROGRAMS: Final = (
    Program("BELL", "a Bell pair: H, CX", "00 and 11, about half each", bell),
    Program("GHZ3", "a three-qubit GHZ state: H, two CX", "000 and 111, about half each", ghz),
    Program("QFT3", "the Fourier state of 5 on three qubits, then the inverse QFT",
            "101 every time, the number 5", qft3, 1000),
    Program("ABSTRACT_PARAMETER", "H, then a phase gate controlled on 00 (phi = pi/2)",
            "000 and 100, about half each: q[2] reads 0 or 1, and the others read 0", abstract_parameter, 1000),
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
    Program("BV4", "Bernstein-Vazirani with the hidden string 1011",
            "1011 every time (the key of the site reads 01101)", bv4, 1000),
    Program("ADD_CONST", "3 + 3 on three bits", "6 every time (the key of the site reads 110)", add_const, 1000),
    Program("GROVER3", "exact Grover on three qubits, one winner", "6 every time (the key of the site reads 110)",
            grover3, 1000),
    Program("HELLO", "the word hello on 25 qubits, no two-qubit gate", "hello every time", hello, 1000),
    Program("ISING2", "five Trotter steps of two spins", "11 most often, about 0.87", ising2, 1000),
)
