"""The example qrisp/constrained_mixer in Qrisp code: each job gate by gate, on Qrisp's own emulator, with no noise.

Run it where Qrisp is installed. In a terminal on Binder, which starts at the top of the clone:

    cd examples/qrisp/constrained_mixer && python emulate_qrisp.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/qrisp/constrained_mixer/emulate_qrisp.py

It prints the share of each key of each job in the form of emulate.sh: the first character of a key is the highest
classical bit, as on the site. The shares are those that qrisp_emulated.json stores, to 8 places, on the kind of
computer that made it; Qrisp rounds its own shares to 5 or 6 places, so another kind of computer can differ by about
0.00001.

Its text was made with Qrisp, examples/qrisp/write_manifests.py. Its Qrisp program is in examples/qrisp/programs.py.

examples/tools/write_qrisp_scripts.py writes this file from the text of each job, with the same calls as the emulator of
the examples. It needs nothing else from the clone, so you can copy it anywhere.
"""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from math import pi

from qrisp import QuantumCircuit


def constrained_mixer():
    """The job CONSTRAINED_MIXER: CONSTRAINED_MIXER.qasm, on 4 qubits."""
    qc = QuantumCircuit(4, 4)
    qc.h(0)
    qc.x(2)
    qc.x(0)
    qc.h(2)
    qc.rz(-0.3926990816987241, 0)
    qc.x(2)
    qc.rz(-0.3926990816987241, 2)
    qc.x(1)
    qc.h(1)
    qc.x(1)
    qc.rz(-0.3926990816987241, 1)
    qc.cx(1, 2)
    qc.rz(0.3926990816987241, 2)
    qc.cx(0, 2)
    qc.rz(-0.3926990816987241, 2)
    qc.cx(1, 2)
    qc.rz(0.3926990816987241, 2)
    qc.cx(0, 1)
    qc.cx(0, 2)
    qc.rz(0.3926990816987241, 1)
    qc.x(2)
    qc.cx(0, 1)
    qc.h(2)
    qc.x(0)
    qc.rz(pi / 4, 1)
    qc.cx(2, 3)
    qc.h(0)
    qc.cx(0, 3)
    qc.rz(-1.5707963267948963, 3)
    qc.cx(0, 3)
    qc.h(0)
    qc.cx(2, 3)
    qc.x(0)
    qc.h(2)
    qc.rz(pi / 4, 0)
    qc.x(2)
    qc.rz(pi / 4, 2)
    qc.cx(1, 2)
    qc.rz(-pi / 4, 2)
    qc.cx(0, 2)
    qc.rz(pi / 4, 2)
    qc.cx(1, 2)
    qc.rz(-pi / 4, 2)
    qc.cx(0, 1)
    qc.cx(0, 2)
    qc.rz(-pi / 4, 1)
    qc.x(2)
    qc.cx(0, 1)
    qc.h(2)
    qc.x(0)
    qc.rz(0.3926990816987241, 1)
    qc.cx(2, 3)
    qc.h(0)
    qc.cx(0, 3)
    qc.rz(1.5707963267948963, 3)
    qc.cx(0, 3)
    qc.h(0)
    qc.cx(2, 3)
    qc.x(0)
    qc.h(2)
    qc.rz(0.3926990816987241, 0)
    qc.x(2)
    qc.rz(0.3926990816987241, 2)
    qc.cx(1, 2)
    qc.rz(-0.3926990816987241, 2)
    qc.cx(0, 2)
    qc.rz(0.3926990816987241, 2)
    qc.cx(1, 2)
    qc.rz(-0.3926990816987241, 2)
    qc.cx(0, 1)
    qc.cx(0, 2)
    qc.rz(-0.3926990816987241, 1)
    qc.x(2)
    qc.cx(0, 1)
    qc.h(2)
    qc.x(1)
    qc.x(0)
    qc.h(1)
    qc.h(0)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    qc.measure(3, 3)
    return qc


# Each job and the function that builds its circuit.
JOBS = {
    "CONSTRAINED_MIXER": constrained_mixer,
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
