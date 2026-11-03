"""A parsed Circuit on Qrisp's own emulator, by Qrisp's gate methods, so all three forms of text take one path."""

# The emulator Qrisp runs by default has no model of noise, so this has none.
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Final

from circuit import Circuit, circuit_of
from emulate import jobs_of
from qrisp import QuantumCircuit

PLACES: Final = 8                                                     # Qrisp itself rounds to 5 or 6 places
SAME_NAME: Final = ("x", "y", "z", "h", "s", "t", "rx", "ry", "rz", "u3", "cx", "cy", "cz", "rxx")
OTHER_NAME: Final = {"sdg": "s_dg", "tdg": "t_dg", "move": "swap"}   # our `move` is a swap: see gates.py


def _r(qc: QuantumCircuit, qubits: tuple, theta: float, phi: float) -> None:
    """Qrisp has no `r`: turn the axis to X, rotate about X, and turn it back."""
    qc.rz(-phi, qubits[0])
    qc.rx(theta, qubits[0])
    qc.rz(phi, qubits[0])


def _crz(qc: QuantumCircuit, qubits: tuple, theta: float) -> None:
    """Qrisp has no `crz` method: half the angle on the target, then two CX flip the sign of the other half."""
    control, target = qubits
    qc.rz(theta / 2, target)
    qc.cx(control, target)
    qc.rz(-theta / 2, target)
    qc.cx(control, target)


BUILT_FROM_OTHERS: Final = {"r": _r, "crz": _crz}


def add_gate(qc: QuantumCircuit, name: str, qubits: tuple, args: tuple) -> None:
    """One gate of ours, by the Qrisp method that equals it up to a global phase."""
    if name in BUILT_FROM_OTHERS:
        BUILT_FROM_OTHERS[name](qc, qubits, *args)
    elif name in OTHER_NAME or name in SAME_NAME:
        getattr(qc, OTHER_NAME.get(name, name))(*args, *qubits)
    else:
        raise ValueError(f"no Qrisp gate for: {name}")


def qrisp_circuit(circuit: Circuit) -> QuantumCircuit:
    """The gates in Qrisp, on the same qubit numbers; the first character of a key is the highest classical bit."""
    qc = QuantumCircuit(max(circuit.qubits) + 1, len(circuit.bits))
    for name, qubits, args in circuit.ops:
        add_gate(qc, name, qubits, args)
    for clbit, qubit in enumerate(reversed(circuit.bits)):
        qc.measure(qubit, clbit)
    return qc


def qrisp_shares(circuit: Circuit) -> dict:
    """The share of each key on Qrisp's emulator, in our order of a key, with no progress bar."""
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return {key: float(share) for key, share in qrisp_circuit(circuit).run().items()}


def folder_shares(folder: Path) -> dict:
    """The shares of each job of a folder on Qrisp's emulator, to 8 places, with the keys in order."""
    shares = {job["name"]: qrisp_shares(circuit_of(folder / job["file"])) for job in jobs_of(folder)}
    return {name: {key: round(said[key], PLACES) for key in sorted(said)} for name, said in shares.items()}
