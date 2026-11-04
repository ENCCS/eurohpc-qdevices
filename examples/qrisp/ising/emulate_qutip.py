"""The example qrisp/ising in QuTiP code: each job gate by gate in qutip-qip, run with no noise.

Run it where QuTiP and qutip-qip are installed. In a terminal on Binder, from File > New > Terminal, which starts at the
top of the clone:

    cd examples/qrisp/ising && python emulate_qutip.py

From the top of a clone of your own, with pixi:

    pixi run --manifest-path examples/qrisp/pixi.toml python examples/qrisp/ising/emulate_qutip.py

It prints the share of each key of each job in the form of emulate.sh: the first character of a key is the highest
classical bit, as on the site. The shares are those that qutip_emulated.json stores, to 8 places.

To send a circuit of your own without writing OpenQASM, write it in QuTiP as below. The first line prints the OpenQASM 2
text that qutip-qip writes from each circuit, and the second keeps that of one job:

    python emulate_qutip.py --qasm
    python emulate_qutip.py --qasm JOB > mine.qasm

examples/tools/write_qutip_scripts.py writes this file from the text of each job. It needs nothing else from the clone,
so you can copy it anywhere.
"""

import re
import sys

import numpy as np
from qutip import basis
from qutip_qip.circuit import QubitCircuit
from qutip_qip.qasm import circuit_to_qasm_str


def ising():
    """The job ISING: ISING.qasm, on 6 qubits."""
    qc = QubitCircuit(6)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("RZ", targets=[2], arg_value=-0.4)
    qc.add_gate("RZ", targets=[4], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("RZ", targets=[1], arg_value=-0.4)
    qc.add_gate("RZ", targets=[3], arg_value=-0.4)
    qc.add_gate("RZ", targets=[5], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("RZ", targets=[1], arg_value=0.4)
    qc.add_gate("RZ", targets=[0], arg_value=0.4)
    qc.add_gate("RZ", targets=[3], arg_value=0.4)
    qc.add_gate("RZ", targets=[2], arg_value=0.4)
    qc.add_gate("RZ", targets=[5], arg_value=0.4)
    qc.add_gate("RZ", targets=[4], arg_value=0.4)
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("RZ", targets=[2], arg_value=-0.4)
    qc.add_gate("RZ", targets=[4], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("RZ", targets=[1], arg_value=-0.4)
    qc.add_gate("RZ", targets=[3], arg_value=-0.4)
    qc.add_gate("RZ", targets=[5], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("RZ", targets=[1], arg_value=0.4)
    qc.add_gate("RZ", targets=[0], arg_value=0.4)
    qc.add_gate("RZ", targets=[3], arg_value=0.4)
    qc.add_gate("RZ", targets=[2], arg_value=0.4)
    qc.add_gate("RZ", targets=[5], arg_value=0.4)
    qc.add_gate("RZ", targets=[4], arg_value=0.4)
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("RZ", targets=[2], arg_value=-0.4)
    qc.add_gate("RZ", targets=[4], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("RZ", targets=[1], arg_value=-0.4)
    qc.add_gate("RZ", targets=[3], arg_value=-0.4)
    qc.add_gate("RZ", targets=[5], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("RZ", targets=[1], arg_value=0.4)
    qc.add_gate("RZ", targets=[0], arg_value=0.4)
    qc.add_gate("RZ", targets=[3], arg_value=0.4)
    qc.add_gate("RZ", targets=[2], arg_value=0.4)
    qc.add_gate("RZ", targets=[5], arg_value=0.4)
    qc.add_gate("RZ", targets=[4], arg_value=0.4)
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("RZ", targets=[2], arg_value=-0.4)
    qc.add_gate("RZ", targets=[4], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("RZ", targets=[1], arg_value=-0.4)
    qc.add_gate("RZ", targets=[3], arg_value=-0.4)
    qc.add_gate("RZ", targets=[5], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("RZ", targets=[1], arg_value=0.4)
    qc.add_gate("RZ", targets=[0], arg_value=0.4)
    qc.add_gate("RZ", targets=[3], arg_value=0.4)
    qc.add_gate("RZ", targets=[2], arg_value=0.4)
    qc.add_gate("RZ", targets=[5], arg_value=0.4)
    qc.add_gate("RZ", targets=[4], arg_value=0.4)
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("RZ", targets=[2], arg_value=-0.4)
    qc.add_gate("RZ", targets=[4], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[1], targets=[2])
    qc.add_gate("CNOT", controls=[3], targets=[4])
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("RZ", targets=[1], arg_value=-0.4)
    qc.add_gate("RZ", targets=[3], arg_value=-0.4)
    qc.add_gate("RZ", targets=[5], arg_value=-0.4)
    qc.add_gate("CNOT", controls=[0], targets=[1])
    qc.add_gate("CNOT", controls=[2], targets=[3])
    qc.add_gate("CNOT", controls=[4], targets=[5])
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    qc.add_gate("RZ", targets=[1], arg_value=0.4)
    qc.add_gate("RZ", targets=[0], arg_value=0.4)
    qc.add_gate("RZ", targets=[3], arg_value=0.4)
    qc.add_gate("RZ", targets=[2], arg_value=0.4)
    qc.add_gate("RZ", targets=[5], arg_value=0.4)
    qc.add_gate("RZ", targets=[4], arg_value=0.4)
    qc.add_gate("H", targets=[1])
    qc.add_gate("H", targets=[0])
    qc.add_gate("H", targets=[3])
    qc.add_gate("H", targets=[2])
    qc.add_gate("H", targets=[5])
    qc.add_gate("H", targets=[4])
    return qc


# Each job: the function that builds its circuit, and the qubit that each character of a key reads, in order.
JOBS = {
    "ISING": (ising, [5, 4, 3, 2, 1, 0]),
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


def to_qasm(qc, read):
    """The OpenQASM 2 text that qutip-qip writes for a circuit, with its measurements; Euro-Q-Exa compiles it.

    qutip-qip 0.4.2 writes no H and no CZ, so H goes under its older name SNOT, and CZ as H, CX, H on the target.
    It also leaves the semicolon off each measure line and writes a small angle as 1e-05, where OpenQASM 2 needs
    1.0e-05: the last two lines put both right.
    qutip-qip refuses some other gates, CY and CPHASE among them, and writes some as a gate that the text defines,
    SWAP among them: build those from the gates above.
    """
    out = QubitCircuit(qc.N, num_cbits=len(read))
    for gate in qc.gates:
        if getattr(gate, "classical_controls", True):  # a measurement, or a gate under a classical bit
            raise ValueError(f"to_qasm writes gates only, and adds the measurements of read: not {gate}")
        if gate.name == "CZ":
            out.add_gate("SNOT", targets=gate.targets)
            out.add_gate("CNOT", controls=gate.controls, targets=gate.targets)
            out.add_gate("SNOT", targets=gate.targets)
        else:
            name = "SNOT" if gate.name == "H" else gate.name
            out.add_gate(name, targets=gate.targets, controls=gate.controls, arg_value=gate.arg_value)
    for clbit, qubit in enumerate(reversed(read)):
        out.add_measurement("M", targets=[qubit], classical_store=clbit)
    text = re.sub(r"^(measure [^;\n]*)$", r"\1;", circuit_to_qasm_str(out), flags=re.M)
    return re.sub(r"(?<![\w.])(\d+)(e[-+]?\d+)", r"\1.0\2", text)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--qasm"]:
        names = sys.argv[2:] or list(JOBS)
        if unknown := [name for name in names if name not in JOBS]:
            sys.exit(f"no job {', '.join(unknown)} here; the jobs: {', '.join(JOBS)}")
        for name in names:
            build, read = JOBS[name]
            print(("" if len(names) == 1 else f"// {name}\n") + to_qasm(build(), read), end="")
    else:
        for name, (build, read) in JOBS.items():
            print(f"{name}: QuTiP, run now, no noise  {top(shares_of(build(), read))}")
        print("Emulated on this computer: nothing was sent.")
