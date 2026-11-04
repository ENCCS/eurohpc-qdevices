"""A parsed Circuit on Qrisp's own emulator, by Qrisp's gate methods, so all three forms of text take one path."""

# The emulator Qrisp runs by default has no model of noise, so this has none.
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Final

from circuit import Circuit, circuit_of
from emulate import jobs_of
from gates import MOVE_WHY
from qrisp import QuantumCircuit

PLACES: Final = 8                                                     # Qrisp itself rounds to 5 or 6 places
SAME_NAME: Final = ("x", "y", "z", "h", "s", "t", "rx", "ry", "rz", "u3", "cx", "cy", "cz", "rxx")
OTHER_NAME: Final = {"sdg": "s_dg", "tdg": "t_dg", "move": "swap"}   # our `move` is a swap: see gates.py


WHY: Final = {
    "r": "Qrisp's own r(theta, phi) is our r(theta, phi - pi/2): turn the axis to X, rotate about X, and turn it back",
    "crz": "Qrisp has no crz method: half the angle on the target, then two CX flip the sign of the other half",
    "sdg": "Qrisp names it s_dg", "tdg": "Qrisp names it t_dg",
    "move": MOVE_WHY}


@dataclass(frozen=True)
class Call:
    """One call of a Qrisp gate method: its name, its angles then its qubits, and the gate of the text."""

    method: str
    args: tuple
    ours: str = ""

    def apply(self, qc: QuantumCircuit) -> None:
        """Make this call on a QuantumCircuit."""
        getattr(qc, self.method)(*self.args)


def _r(qubits: tuple, theta: float, phi: float) -> tuple:
    q = qubits[0]
    return Call("rz", (-phi, q), "r"), Call("rx", (theta, q), "r"), Call("rz", (phi, q), "r")


def _crz(qubits: tuple, theta: float) -> tuple:
    control, target = qubits
    return (Call("rz", (theta / 2, target), "crz"), Call("cx", (control, target), "crz"),
            Call("rz", (-theta / 2, target), "crz"), Call("cx", (control, target), "crz"))


BUILT_FROM_OTHERS: Final = {"r": _r, "crz": _crz}


def calls_of(name: str, qubits: tuple, args: tuple) -> tuple:
    """One gate of ours as the Qrisp calls that equal it up to a global phase."""
    if name in BUILT_FROM_OTHERS:
        return BUILT_FROM_OTHERS[name](qubits, *args)
    if name in OTHER_NAME or name in SAME_NAME:
        return (Call(OTHER_NAME.get(name, name), (*args, *qubits), name),)
    raise ValueError(f"no Qrisp gate for: {name}")


def add_gate(qc: QuantumCircuit, name: str, qubits: tuple, args: tuple) -> None:
    """One gate of ours, by the Qrisp methods that equal it up to a global phase."""
    for call in calls_of(name, qubits, args):
        call.apply(qc)


def qrisp_calls(circuit: Circuit) -> tuple:
    """The Qrisp calls of a circuit, in the order of its text, on the same qubit numbers."""
    return tuple(call for name, qubits, args in circuit.ops for call in calls_of(name, qubits, args))


def measures(circuit: Circuit) -> tuple:
    """(qubit, classical bit) of each measurement: classical bit 0 is the last character of a key."""
    return tuple((qubit, clbit) for clbit, qubit in enumerate(reversed(circuit.bits)))


def qrisp_circuit(circuit: Circuit) -> QuantumCircuit:
    """The gates in Qrisp, on the same qubit numbers; the first character of a key is the highest classical bit."""
    qc = QuantumCircuit(max(circuit.qubits) + 1, len(circuit.bits))
    for call in qrisp_calls(circuit):
        call.apply(qc)
    for qubit, clbit in measures(circuit):
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
