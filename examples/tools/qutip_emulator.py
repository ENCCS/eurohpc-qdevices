"""A parsed Circuit on QuTiP, by qutip-qip's gates, so all three forms of text take one path. It has no noise.

It runs the gates on the state vector from |0...0> of the qubits the circuit uses, renumbered from 0 in their order,
and gives the share of each key from the final state. QuTiP holds qubit 0 as the first factor of a tensor product, so
qubit 0 is the highest bit of an index into its state; a key reads the qubits of `Circuit.bits` in their order, the
highest classical bit first, as ours and Qrisp's do.
"""

from __future__ import annotations

from math import pi
from pathlib import Path
from typing import Final

import numpy as np
from circuit import Circuit, circuit_of
from emulate import jobs_of
from qutip import basis
from qutip_qip.circuit import QubitCircuit

PLACES: Final = 8
SMALLEST: Final = 1e-12                                               # a share at or below it is float noise
ONE_QUBIT: Final = {"x": "X", "y": "Y", "z": "Z", "h": "H", "s": "S", "t": "T", "rx": "RX", "ry": "RY", "rz": "RZ",
                    "u3": "QASMU", "r": "R"}
CONTROLLED: Final = {"cx": "CNOT", "cy": "CY", "cz": "CZ", "crz": "CRZ"}  # the first qubit controls the second
TWO_QUBIT: Final = {"move": "SWAP"}                                   # our `move` is a swap: see gates.py


def _arg(args: tuple):
    return None if not args else args[0] if len(args) == 1 else list(args)


def _sdg(qc: QubitCircuit, qubits: tuple) -> None:
    """qutip-qip has no S dagger: RZ(-pi/2) is S dagger times exp(i pi/4)."""
    qc.add_gate("RZ", targets=[qubits[0]], arg_value=-pi / 2)


def _tdg(qc: QubitCircuit, qubits: tuple) -> None:
    """qutip-qip has no T dagger: RZ(-pi/4) is T dagger times exp(i pi/8)."""
    qc.add_gate("RZ", targets=[qubits[0]], arg_value=-pi / 4)


def _rxx(qc: QubitCircuit, qubits: tuple, theta: float) -> None:
    """qutip-qip's MS gate with its axis at phi = 0 is exp(-i theta/2 XX), our `rxx`."""
    qc.add_gate("MS", targets=list(qubits), arg_value=(theta, 0.0))


BUILT_FROM_OTHERS: Final = {"sdg": _sdg, "tdg": _tdg, "rxx": _rxx}


def add_gate(qc: QubitCircuit, name: str, qubits: tuple, args: tuple) -> None:
    """One gate of ours, by the qutip-qip gate that equals it up to a global phase."""
    if name in BUILT_FROM_OTHERS:
        BUILT_FROM_OTHERS[name](qc, qubits, *args)
    elif name in ONE_QUBIT:
        qc.add_gate(ONE_QUBIT[name], targets=[qubits[0]], arg_value=_arg(args))
    elif name in CONTROLLED:
        qc.add_gate(CONTROLLED[name], controls=[qubits[0]], targets=[qubits[1]], arg_value=_arg(args))
    elif name in TWO_QUBIT:
        qc.add_gate(TWO_QUBIT[name], targets=list(qubits))
    else:
        raise ValueError(f"no qutip-qip gate for: {name}")


def qutip_circuit(circuit: Circuit) -> QubitCircuit:
    """The gates in qutip-qip on the qubits used, renumbered from 0, with no measurement.

    The shares come from the final state. An idle qubit stays in |0> and changes no share, so it is left out.
    """
    qc = QubitCircuit(len(circuit.qubits))
    for name, qubits, args in circuit.renumbered().ops:
        add_gate(qc, name, qubits, args)
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
