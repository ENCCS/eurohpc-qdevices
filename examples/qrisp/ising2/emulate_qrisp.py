"""The example qrisp/ising2 in Qrisp code: each job gate by gate, on Qrisp's own emulator, with no noise.

Run it where Qrisp is installed. In a terminal on Binder, from File > New > Terminal, which starts at the top of the
clone:

    cd examples/qrisp/ising2 && python emulate_qrisp.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/qrisp/ising2/emulate_qrisp.py

It prints the share of each key of each job in the form of emulate.sh: the first character of a key is the highest
classical bit, as on the site. The shares are those that qrisp_emulated.json stores, to 8 places, on the kind of
computer that made it; Qrisp rounds its own shares to 5 or 6 places, so another kind of computer can differ by about
0.00001.

Its text was made with Qrisp, examples/qrisp/write_manifests.py. Its Qrisp program is the function ising2 of
examples/qrisp/programs.py.

To send a circuit of your own without writing OpenQASM, write it in Qrisp as below. The first line prints the OpenQASM 2
text of each circuit, as examples/qrisp/qasm2.py of the clone writes it, and the second keeps that of one job:

    python emulate_qrisp.py --qasm
    python emulate_qrisp.py --qasm JOB > mine.qasm

examples/tools/write_qrisp_scripts.py writes this file from the text of each job, with the same calls as the emulator of
the examples. It needs nothing else from the clone, but --qasm, which uses examples/qrisp/qasm2.py.
"""

import sys
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from qrisp import QuantumCircuit


def ising2():
    """The job ISING2: ISING2.qasm, on 2 qubits."""
    qc = QuantumCircuit(2, 2)
    qc.cx(0, 1)
    qc.rz(-0.9666438934122439, 1)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    qc.rz(-1.1599726720946928, 1)
    qc.rz(-1.1599726720946928, 0)
    qc.h(1)
    qc.h(0)
    qc.cx(0, 1)
    qc.rz(-0.9666438934122439, 1)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    qc.rz(-1.1599726720946928, 1)
    qc.rz(-1.1599726720946928, 0)
    qc.h(1)
    qc.h(0)
    qc.cx(0, 1)
    qc.rz(-0.9666438934122439, 1)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    qc.rz(-1.1599726720946928, 1)
    qc.rz(-1.1599726720946928, 0)
    qc.h(1)
    qc.h(0)
    qc.cx(0, 1)
    qc.rz(-0.9666438934122439, 1)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    qc.rz(-1.1599726720946928, 1)
    qc.rz(-1.1599726720946928, 0)
    qc.h(1)
    qc.h(0)
    qc.cx(0, 1)
    qc.rz(-0.9666438934122439, 1)
    qc.cx(0, 1)
    qc.h(1)
    qc.h(0)
    qc.rz(-1.1599726720946928, 1)
    qc.rz(-1.1599726720946928, 0)
    qc.h(1)
    qc.h(0)
    # the measurements, qubit then classical bit: bit 0 is the last character of a key
    qc.measure(0, 0)
    qc.measure(1, 1)
    return qc


# Each job and the function that builds its circuit.
JOBS = {
    "ISING2": ising2,
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


def to_qasm(qc):
    """The OpenQASM 2 text of a circuit, by examples/qrisp/qasm2.py of the clone, which writes the Qrisp examples.

    Qrisp 0.9.10 writes OpenQASM through a package of another framework, so the examples use their own short converter.
    """
    examples = next((p for p in Path(__file__).resolve().parents if (p / "qrisp" / "qasm2.py").exists()), None)
    if examples is None:
        sys.exit("--qasm needs examples/qrisp/qasm2.py: run this file in its folder of a clone")
    sys.path.insert(0, str(examples / "qrisp"))
    from qasm2 import to_qasm2

    return to_qasm2(qc)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--qasm"]:
        names = sys.argv[2:] or list(JOBS)
        if unknown := [name for name in names if name not in JOBS]:
            sys.exit(f"no job {', '.join(unknown)} here; the jobs: {', '.join(JOBS)}")
        for name in names:
            print(("" if len(names) == 1 else f"// {name}\n") + to_qasm(JOBS[name]()), end="")
    else:
        for name, build in JOBS.items():
            print(f"{name}: Qrisp's emulator, run now, no noise  {top(shares_of(build()))}")
        print("Emulated on this computer: nothing was sent.")
