"""A parsed Circuit on QuTiP, by qutip-qip's gates, so all three forms of text take one path. It has no noise.

`gate_steps` gives the qutip-qip gates of a circuit in the order of its text: the emulator builds its QubitCircuit from
them, and write_qutip_scripts.py prints them as the code of each folder's emulate_qutip.py. It runs the gates on the
state vector from |0...0> of the qubits the circuit uses, renumbered from 0 in their order, and gives the share of each
key from the final state. QuTiP holds qubit 0 as the first factor of a tensor product, so qubit 0 is the highest bit of
an index into its state; a key reads the qubits of `Circuit.bits` in their order, the highest classical bit first, as
ours and Qrisp's do.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi
from pathlib import Path
from typing import Final

import numpy as np
from circuit import Circuit, circuit_of
from emulate import jobs_of
from gates import MOVE_WHY
from qutip import basis
from qutip_qip.circuit import QubitCircuit

PLACES: Final = 8
SMALLEST: Final = 1e-12                                               # a share at or below it is float noise
ONE_QUBIT: Final = {"x": "X", "y": "Y", "z": "Z", "h": "H", "s": "S", "t": "T", "rx": "RX", "ry": "RY", "rz": "RZ",
                    "u3": "QASMU", "r": "R"}
CONTROLLED: Final = {"cx": "CNOT", "cy": "CY", "cz": "CZ", "crz": "CRZ"}  # the first qubit controls the second
TWO_QUBIT: Final = {"move": "SWAP"}                                   # our `move` is a swap: see gates.py
WHY: Final = {                                    # how a qutip-qip gate stands for a gate of ours of another name
    "sdg": "qutip-qip has no S dagger: RZ(-pi/2) is S dagger times exp(i pi/4), a global phase no share shows.",
    "tdg": "qutip-qip has no T dagger: RZ(-pi/4) is T dagger times exp(i pi/8), a global phase no share shows.",
    "rxx": "MS, the Mølmer-Sørensen gate, with its axis at phi = 0 is RXX, exp(-i theta/2 XX).",
    "move": MOVE_WHY + ".",
    "u3": "QASMU is RZ(phi) RY(theta) RZ(lambda), the u3 of the text up to a global phase.",
}


@dataclass(frozen=True)
class Step:
    """One qutip-qip gate: its name, its target and control qubits, its angle or angles, and the gate of the text."""

    gate: str
    targets: tuple
    controls: tuple = ()
    arg: float | list | tuple | None = None
    ours: str = ""

    def add_to(self, qc: QubitCircuit) -> None:
        """Add this gate to a QubitCircuit."""
        qc.add_gate(self.gate, targets=list(self.targets), controls=list(self.controls) or None, arg_value=self.arg)


def _arg(args: tuple):
    return None if not args else args[0] if len(args) == 1 else list(args)


def _sdg(qubits: tuple) -> Step:
    return Step("RZ", qubits[:1], arg=-pi / 2, ours="sdg")


def _tdg(qubits: tuple) -> Step:
    return Step("RZ", qubits[:1], arg=-pi / 4, ours="tdg")


def _rxx(qubits: tuple, theta: float) -> Step:
    return Step("MS", tuple(qubits), arg=(theta, 0.0), ours="rxx")


BUILT_FROM_OTHERS: Final = {"sdg": _sdg, "tdg": _tdg, "rxx": _rxx}


def step_of(name: str, qubits: tuple, args: tuple) -> Step:
    """One gate of ours, as the qutip-qip gate that equals it up to a global phase."""
    if name in BUILT_FROM_OTHERS:
        return BUILT_FROM_OTHERS[name](qubits, *args)
    if name in ONE_QUBIT:
        return Step(ONE_QUBIT[name], qubits[:1], arg=_arg(args), ours=name)
    if name in CONTROLLED:
        return Step(CONTROLLED[name], qubits[1:2], qubits[:1], _arg(args), name)
    if name in TWO_QUBIT:
        return Step(TWO_QUBIT[name], tuple(qubits), ours=name)
    raise ValueError(f"no qutip-qip gate for: {name}")


def add_gate(qc: QubitCircuit, name: str, qubits: tuple, args: tuple) -> None:
    """Add one gate of ours to a QubitCircuit, by the qutip-qip gate that equals it up to a global phase."""
    step_of(name, qubits, args).add_to(qc)


def gate_steps(circuit: Circuit) -> tuple:
    """The qutip-qip gates of a circuit, in the order of its text, on the qubits it uses renumbered from 0."""
    return tuple(step_of(name, qubits, args) for name, qubits, args in circuit.renumbered().ops)


def qutip_circuit(circuit: Circuit) -> QubitCircuit:
    """The gates in qutip-qip on the qubits used, renumbered from 0, with no measurement.

    The shares come from the final state. An idle qubit stays in |0> and changes no share, so it is left out.
    """
    qc = QubitCircuit(len(circuit.qubits))
    for step in gate_steps(circuit):
        step.add_to(qc)
    return qc


def keys_of(probabilities: np.ndarray, bits: tuple) -> dict:
    """The share of each key from the probability of each index, with qubit 0 as the highest bit of an index."""
    size = int(probabilities.size).bit_length() - 1
    read = sorted(set(bits))
    tensor = probabilities.reshape([2] * size).sum(axis=tuple(q for q in range(size) if q not in read))
    flat = tensor.reshape(-1)
    out = {}
    for index in np.flatnonzero(flat > SMALLEST):
        bit = {q: int(index) >> (len(read) - 1 - place) & 1 for place, q in enumerate(read)}
        out["".join(str(bit[q]) for q in bits)] = float(flat[index])
    return out


def qutip_shares(circuit: Circuit) -> dict:
    """The share of each key on QuTiP from |0...0>, in our order of a key; keys above 1e-12 only, unrounded."""
    qc = qutip_circuit(circuit)
    final = qc.run(basis([2] * qc.N, [0] * qc.N))
    return keys_of(np.abs(final.full().reshape(-1)) ** 2, circuit.renumbered().bits)


def folder_shares(folder: Path) -> tuple:
    """The shares of each job of a folder on QuTiP, to 8 places with the keys in order, and why a job did not run.

    Only a job with a gate that has no qutip-qip mapping is named as not run; any other error stops the writer.
    """
    shares, not_run = {}, {}
    for job in jobs_of(folder):
        try:
            said = qutip_shares(circuit_of(folder / job["file"]))
        except ValueError as why:
            not_run[job["name"]] = str(why)
            continue
        shares[job["name"]] = {key: round(said[key], PLACES) for key in sorted(said)}
    return shares, not_run
