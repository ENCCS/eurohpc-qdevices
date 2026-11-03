"""The example piastq-bell in QuTiP code: each job gate by gate in qutip-qip, run with no noise.

Run it where QuTiP and qutip-qip are installed. In a terminal on Binder, which starts at the top of the clone:

    cd examples/piastq-bell && python emulate_qutip.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/piastq-bell/emulate_qutip.py

It prints the share of each key of each job in the form of emulate.sh: a key reads qubit 0 first, as the broker gives
it. The shares are those that qutip_emulated.json stores, to 8 places.

examples/tools/write_qutip_scripts.py writes this file from the text of each job. It needs nothing else from the clone,
so you can copy it anywhere.
"""

import numpy as np
from qutip import basis
from qutip_qip.circuit import QubitCircuit


def bell():
    """The job BELL: BELL.json, on 2 qubits."""
    qc = QubitCircuit(2)
    # rxx: MS with its axis at phi = 0 is RXX, exp(-i theta/2 XX).
    qc.add_gate("MS", targets=[0, 1], arg_value=(np.pi / 2, 0.0))  # rxx
    return qc


# Each job: the function that builds its circuit, and the qubit that each character of a key reads, in order.
JOBS = {
    "BELL": (bell, [0, 1]),
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
