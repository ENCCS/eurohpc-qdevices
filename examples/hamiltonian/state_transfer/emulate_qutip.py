"""The example hamiltonian/state_transfer in QuTiP code: each job gate by gate in qutip-qip, run with no noise.

Run it where QuTiP and qutip-qip are installed. In a terminal on Binder, which starts at the top of the clone:

    cd examples/hamiltonian/state_transfer && python emulate_qutip.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/hamiltonian/state_transfer/emulate_qutip.py

It prints the share of each key of each job in the form of emulate.sh: the first character of a key is the highest
classical bit, as on the site. The shares are those that qutip_emulated.json stores, to 8 places.

examples/tools/write_qutip_scripts.py writes this file from the text of each job. It needs nothing else from the clone,
so you can copy it anywhere.
"""

import numpy as np
from qutip import basis
from qutip_qip.circuit import QubitCircuit


def control():
    """The job CONTROL: CONTROL.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    return qc


def main():
    """The job MAIN: MAIN.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


def qrisp():
    """The job QRISP: QRISP.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[2])
    qc.add_gate("CZ", controls=[1], targets=[0])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[1])
    qc.add_gate("RZ", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RZ", targets=[1], arg_value=-0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("CZ", controls=[1], targets=[0])
    qc.add_gate("H", targets=[1])
    qc.add_gate("CZ", controls=[2], targets=[1])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[2])
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RZ", targets=[2], arg_value=-1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[1])
    qc.add_gate("CZ", controls=[2], targets=[1])
    qc.add_gate("H", targets=[1])
    qc.add_gate("CZ", controls=[1], targets=[0])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RZ", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=-1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("CZ", controls=[1], targets=[0])
    qc.add_gate("H", targets=[1])
    qc.add_gate("CZ", controls=[2], targets=[1])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[2])
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RZ", targets=[2], arg_value=-1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[1])
    qc.add_gate("CZ", controls=[2], targets=[1])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[1])
    qc.add_gate("CZ", controls=[1], targets=[0])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RZ", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=-0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("CZ", controls=[1], targets=[0])
    qc.add_gate("H", targets=[1])
    return qc


def repeat():
    """The job REPEAT: REPEAT.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


def half():
    """The job HALF: HALF.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[2], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[2], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


def back():
    """The job BACK: BACK.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


def zero():
    """The job ZERO: ZERO.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


def steps1():
    """The job STEPS1: STEPS1.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=2.221441469079183)
    qc.add_gate("RZ", targets=[2], arg_value=2.221441469079183)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


def steps4():
    """The job STEPS4: STEPS4.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[2], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[2], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[2], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.5553603672697958)
    qc.add_gate("RZ", targets=[2], arg_value=0.5553603672697958)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


def steps8():
    """The job STEPS8: STEPS8.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.13884009181744894)
    qc.add_gate("RZ", targets=[1], arg_value=0.13884009181744894)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[2], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[2], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[2], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[2], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[2], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[2], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[2], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=0.2776801836348979)
    qc.add_gate("RZ", targets=[2], arg_value=0.2776801836348979)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=0.13884009181744894)
    qc.add_gate("RZ", targets=[1], arg_value=0.13884009181744894)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


def order1():
    """The job ORDER1: ORDER1.qasm, on 3 qubits."""
    qc = QubitCircuit(3)
    qc.add_gate("X", targets=[0])
    qc.add_gate("RX", targets=[0], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=np.pi / 2)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("RX", targets=[0], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[1], arg_value=1.1107207345395915)
    qc.add_gate("RZ", targets=[2], arg_value=1.1107207345395915)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("RX", targets=[0], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[1], arg_value=-np.pi / 2)
    qc.add_gate("RX", targets=[2], arg_value=-np.pi / 2)
    return qc


# Each job: the function that builds its circuit, and the qubit that each character of a key reads, in order.
JOBS = {
    "CONTROL": (control, [2, 1, 0]),
    "MAIN": (main, [2, 1, 0]),
    "QRISP": (qrisp, [2, 1, 0]),
    "REPEAT": (repeat, [2, 1, 0]),
    "HALF": (half, [2, 1, 0]),
    "BACK": (back, [2, 1, 0]),
    "ZERO": (zero, [2, 1, 0]),
    "STEPS1": (steps1, [2, 1, 0]),
    "STEPS4": (steps4, [2, 1, 0]),
    "STEPS8": (steps8, [2, 1, 0]),
    "ORDER1": (order1, [2, 1, 0]),
}


def shares_of(qc, read):
    """Run a circuit from |0...0> and give the share of each key above 1e-12; `read` lists the qubits of a key."""
    final = qc.run(basis([2] * qc.N, [0] * qc.N))
    probability = np.abs(final.full().reshape([2] * qc.N)) ** 2                # one axis per qubit, qubit 0 first
    probability = probability.sum(axis=tuple(q for q in range(qc.N) if q not in read))     # over the qubits not read
    by_key = probability.transpose([sorted(read).index(q) for q in read]).reshape(-1)     # the axes in key order
    return {format(index, f"0{len(read)}b"): float(by_key[index]) for index in np.flatnonzero(by_key > 1e-12)}


def top(shares, most=6):
    """The keys with the largest shares, as one line, as emulate.sh prints them."""
    rows = sorted(shares.items(), key=lambda kv: (-round(kv[1], 9), kv[0]))[:most]
    more = f"  and {len(shares) - most} more" if len(shares) > most else ""
    return "  ".join(f"{key}: {value:.3f}" for key, value in rows) + more


if __name__ == "__main__":
    for name, (build, read) in JOBS.items():
        print(f"{name}: QuTiP, run now, no noise  {top(shares_of(build(), read))}")
    print("Emulated on this computer: nothing was sent.")
