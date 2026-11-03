"""The example hamiltonian/state_transfer in Qrisp code: each job gate by gate, on Qrisp's own emulator, with no noise.

Run it where Qrisp is installed. In a terminal on Binder, which starts at the top of the clone:

    cd examples/hamiltonian/state_transfer && python emulate_qrisp.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/hamiltonian/state_transfer/emulate_qrisp.py

It prints the share of each key of each job in the form of emulate.sh: the first character of a key is the highest
classical bit, as on the site. The shares are those that qrisp_emulated.json stores, to 8 places, on the kind of
computer that made it; Qrisp rounds its own shares to 5 or 6 places, so another kind of computer can differ by about
0.00001.

Its text was made with Qrisp and a small function, examples/hamiltonian/write_chain.py.

examples/tools/write_qrisp_scripts.py writes this file from the text of each job, with the same calls as the emulator of
the examples. It needs nothing else from the clone, so you can copy it anywhere.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from math import pi

from qrisp import QuantumCircuit


def control():
    """The job CONTROL: CONTROL.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def main():
    """The job MAIN: MAIN.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def qrisp():
    """The job QRISP: QRISP.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.h(1)
    qc.h(2)
    qc.cz(1, 0)
    qc.h(0)
    qc.h(1)
    qc.rz(0.5553603672697958, 0)
    qc.cx(0, 1)
    qc.rz(-0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    qc.cz(1, 0)
    qc.h(1)
    qc.cz(2, 1)
    qc.h(1)
    qc.h(2)
    qc.rz(1.1107207345395915, 1)
    qc.cx(1, 2)
    qc.rz(-1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.h(2)
    qc.h(1)
    qc.cz(2, 1)
    qc.h(1)
    qc.cz(1, 0)
    qc.h(1)
    qc.h(0)
    qc.cx(0, 1)
    qc.rz(1.1107207345395915, 0)
    qc.rz(-1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    qc.cz(1, 0)
    qc.h(1)
    qc.cz(2, 1)
    qc.h(1)
    qc.h(2)
    qc.rz(1.1107207345395915, 1)
    qc.cx(1, 2)
    qc.rz(-1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.h(2)
    qc.h(1)
    qc.cz(2, 1)
    qc.h(2)
    qc.h(1)
    qc.cz(1, 0)
    qc.h(1)
    qc.h(0)
    qc.cx(0, 1)
    qc.rz(0.5553603672697958, 0)
    qc.rz(-0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    qc.cz(1, 0)
    qc.h(1)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def repeat():
    """The job REPEAT: REPEAT.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def half():
    """The job HALF: HALF.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.5553603672697958, 1)
    qc.rz(0.5553603672697958, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.5553603672697958, 1)
    qc.rz(0.5553603672697958, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def back():
    """The job BACK: BACK.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def zero():
    """The job ZERO: ZERO.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def steps1():
    """The job STEPS1: STEPS1.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(2.221441469079183, 1)
    qc.rz(2.221441469079183, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def steps4():
    """The job STEPS4: STEPS4.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.5553603672697958, 1)
    qc.rz(0.5553603672697958, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.5553603672697958, 1)
    qc.rz(0.5553603672697958, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.5553603672697958, 1)
    qc.rz(0.5553603672697958, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.5553603672697958, 0)
    qc.rz(0.5553603672697958, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.5553603672697958, 1)
    qc.rz(0.5553603672697958, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def steps8():
    """The job STEPS8: STEPS8.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(0.13884009181744894, 0)
    qc.rz(0.13884009181744894, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.2776801836348979, 1)
    qc.rz(0.2776801836348979, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.2776801836348979, 1)
    qc.rz(0.2776801836348979, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.2776801836348979, 1)
    qc.rz(0.2776801836348979, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.2776801836348979, 1)
    qc.rz(0.2776801836348979, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.2776801836348979, 1)
    qc.rz(0.2776801836348979, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.2776801836348979, 1)
    qc.rz(0.2776801836348979, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.2776801836348979, 1)
    qc.rz(0.2776801836348979, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.2776801836348979, 0)
    qc.rz(0.2776801836348979, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(0.2776801836348979, 1)
    qc.rz(0.2776801836348979, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(0.13884009181744894, 0)
    qc.rz(0.13884009181744894, 1)
    qc.cx(0, 1)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


def order1():
    """The job ORDER1: ORDER1.qasm, on 3 qubits."""
    qc = QuantumCircuit(3, 3)
    qc.x(0)
    qc.rx(pi / 2, 0)
    qc.rx(pi / 2, 1)
    qc.rx(pi / 2, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.cx(0, 1)
    qc.rx(1.1107207345395915, 0)
    qc.rz(1.1107207345395915, 1)
    qc.cx(0, 1)
    qc.cx(1, 2)
    qc.rx(1.1107207345395915, 1)
    qc.rz(1.1107207345395915, 2)
    qc.cx(1, 2)
    qc.rx(-pi / 2, 0)
    qc.rx(-pi / 2, 1)
    qc.rx(-pi / 2, 2)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    return qc


# Each job and the function that builds its circuit.
JOBS = {
    "CONTROL": control,
    "MAIN": main,
    "QRISP": qrisp,
    "REPEAT": repeat,
    "HALF": half,
    "BACK": back,
    "ZERO": zero,
    "STEPS1": steps1,
    "STEPS4": steps4,
    "STEPS8": steps8,
    "ORDER1": order1,
}


def shares_of(qc):
    """Run a circuit on Qrisp's emulator, with no progress bar, and give the share of each key."""
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return {key: float(share) for key, share in qc.run().items()}


def top(shares, most=6):
    """The keys with the largest shares, as one line, as emulate.sh prints them."""
    rows = sorted(shares.items(), key=lambda kv: (-round(kv[1], 9), kv[0]))[:most]
    more = f"  and {len(shares) - most} more" if len(shares) > most else ""
    return "  ".join(f"{key}: {value:.3f}" for key, value in rows) + more


if __name__ == "__main__":
    for name, build in JOBS.items():
        print(f"{name}: Qrisp's emulator, run now, no noise  {top(shares_of(build()))}")
    print("Emulated on this computer: nothing was sent.")
