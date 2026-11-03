"""The example piastq-bell in Qrisp code: each job gate by gate, on Qrisp's own emulator, with no noise.

Run it where Qrisp is installed. In a terminal on Binder, which starts at the top of the clone:

    cd examples/piastq-bell && python emulate_qrisp.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/piastq-bell/emulate_qrisp.py

It prints the share of each key of each job in the form of emulate.sh: a key reads qubit 0 first, as the broker gives
it. The shares are those that qrisp_emulated.json stores, to 8 places, on the kind of computer that made it; Qrisp
rounds its own shares to 5 or 6 places, so another kind of computer can differ by about 0.00001.

examples/tools/write_qrisp_scripts.py writes this file from the text of each job, with the same calls as the emulator of
the examples. It needs nothing else from the clone, so you can copy it anywhere.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from math import pi

from qrisp import QuantumCircuit


def bell():
    """The job BELL: BELL.json, on 2 qubits."""
    qc = QuantumCircuit(2, 2)
    qc.rxx(pi / 2, 0, 1)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(1, 0)
    qc.measure(0, 1)
    return qc


# Each job and the function that builds its circuit.
JOBS = {
    "BELL": bell,
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
