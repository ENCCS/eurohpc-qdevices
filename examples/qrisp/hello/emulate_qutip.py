"""The example qrisp/hello in QuTiP code: each job gate by gate in qutip-qip, run with no noise.

Run it where QuTiP and qutip-qip are installed. In a terminal on Binder, which starts at the top of the clone:

    cd examples/qrisp/hello && python emulate_qutip.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/qrisp/hello/emulate_qutip.py

It prints the share of each key of each job in the form of emulate.sh: the first character of a key is the highest
classical bit, as on the site. The shares are those that qutip_emulated.json stores, to 8 places. The job HELLO runs on
25 qubits, a state of 2**25 amplitudes: it takes about 25 seconds and 1.1 GB of memory on a laptop.

examples/tools/write_qutip_scripts.py writes this file from the text of each job. It needs nothing else from the clone,
so you can copy it anywhere.
"""

import numpy as np
from qutip import basis
from qutip_qip.circuit import QubitCircuit


def hello():
    """The job HELLO: HELLO.qasm, on 25 qubits."""
    qc = QubitCircuit(25)
    qc.add_gate("X", targets=[0])
    qc.add_gate("X", targets=[1])
    qc.add_gate("X", targets=[2])
    qc.add_gate("X", targets=[7])
    qc.add_gate("X", targets=[10])
    qc.add_gate("X", targets=[11])
    qc.add_gate("X", targets=[13])
    qc.add_gate("X", targets=[15])
    qc.add_gate("X", targets=[16])
    qc.add_gate("X", targets=[18])
    qc.add_gate("X", targets=[21])
    qc.add_gate("X", targets=[22])
    qc.add_gate("X", targets=[23])
    return qc


# Each job: the function that builds its circuit, and the qubit that each character of a key reads, in order.
JOBS = {
    "HELLO": (hello, [24, 23, 22, 21, 20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]),
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
