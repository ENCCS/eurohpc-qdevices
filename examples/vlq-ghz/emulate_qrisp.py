"""The example vlq-ghz in Qrisp code: each job gate by gate, on Qrisp's own emulator, with no noise.

Run it where Qrisp is installed. In a terminal on Binder, which starts at the top of the clone:

    cd examples/vlq-ghz && python emulate_qrisp.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/vlq-ghz/emulate_qrisp.py

It prints the share of each key of each job in the form of emulate.sh: the first character of a key is the highest
classical bit, as on the site. The shares are those that qrisp_emulated.json stores, to 8 places, on the kind of
computer that made it; Qrisp rounds its own shares to 5 or 6 places, so another kind of computer can differ by about
0.00001.

examples/tools/write_qrisp_scripts.py writes this file from the text of each job, with the same calls as the emulator of
the examples. It needs nothing else from the clone, so you can copy it anywhere.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from math import pi

from qrisp import QuantumCircuit


def ghz():
    """The job GHZ: GHZ.qasm, on 25 qubits."""
    qc = QuantumCircuit(25, 5)
    # r: Qrisp has no r: turn the axis to X, rotate about X, and turn it back
    qc.rz(-pi / 2, 0)  # r
    qc.rx(pi / 2, 0)  # r
    qc.rz(pi / 2, 0)  # r
    # move: our move is a swap of a qubit and the resonator, see examples/tools/gates.py
    qc.swap(0, 24)  # move
    qc.rz(pi / 2, 1)  # r
    qc.rx(pi / 2, 1)  # r
    qc.rz(-pi / 2, 1)  # r
    qc.cz(1, 24)
    qc.rz(-pi / 2, 1)  # r
    qc.rx(pi / 2, 1)  # r
    qc.rz(pi / 2, 1)  # r
    qc.rz(pi / 2, 2)  # r
    qc.rx(pi / 2, 2)  # r
    qc.rz(-pi / 2, 2)  # r
    qc.cz(2, 24)
    qc.rz(-pi / 2, 2)  # r
    qc.rx(pi / 2, 2)  # r
    qc.rz(pi / 2, 2)  # r
    qc.rz(pi / 2, 3)  # r
    qc.rx(pi / 2, 3)  # r
    qc.rz(-pi / 2, 3)  # r
    qc.cz(3, 24)
    qc.rz(-pi / 2, 3)  # r
    qc.rx(pi / 2, 3)  # r
    qc.rz(pi / 2, 3)  # r
    qc.rz(pi / 2, 4)  # r
    qc.rx(pi / 2, 4)  # r
    qc.rz(-pi / 2, 4)  # r
    qc.cz(4, 24)
    qc.rz(-pi / 2, 4)  # r
    qc.rx(pi / 2, 4)  # r
    qc.rz(pi / 2, 4)  # r
    qc.swap(0, 24)  # move
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    qc.measure(3, 3)
    qc.measure(4, 4)
    return qc


# Each job and the function that builds its circuit.
JOBS = {
    "GHZ": ghz,
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
