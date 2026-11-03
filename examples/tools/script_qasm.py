"""The part of emulate_qutip.py and emulate_qrisp.py that writes OpenQASM 2, for the folders of Euro-Q-Exa alone.

Euro-Q-Exa takes OpenQASM 2 and compiles it. VLQ takes OpenQASM 3 in its own gates and Piast-Q the broker's list of
operations, so their scripts have no such part. The two writers of the scripts add these texts as they are.
"""

from typing import Final

SITE: Final = "euroqexa"

QUTIP_IMPORTS: Final = "import re\nimport sys\n\n"
QUTIP_EXTRA_IMPORT: Final = "from qutip_qip.qasm import circuit_to_qasm_str\n"
QUTIP_HELP: Final = ("To send a circuit of your own without writing OpenQASM, write it in QuTiP as below. The first "
                     "line prints the OpenQASM 2 text that qutip-qip writes from each circuit, and the second keeps "
                     "that of one job:",
                     "    python emulate_qutip.py --qasm\n    python emulate_qutip.py --qasm JOB > mine.qasm")
QUTIP_TO_QASM: Final = '''

def to_qasm(qc, read):
    """The OpenQASM 2 text that qutip-qip writes for a circuit, with its measurements; Euro-Q-Exa compiles it.

    qutip-qip 0.4.2 writes no H and no CZ, so H goes under its older name SNOT, and CZ as H, CX, H on the target.
    It also leaves the semicolon off each measure line, and the last line puts it back.
    """
    out = QubitCircuit(qc.N, num_cbits=len(read))
    for gate in qc.gates:
        if gate.name == "CZ":
            out.add_gate("SNOT", targets=gate.targets)
            out.add_gate("CNOT", controls=gate.controls, targets=gate.targets)
            out.add_gate("SNOT", targets=gate.targets)
        else:
            name = "SNOT" if gate.name == "H" else gate.name
            out.add_gate(name, targets=gate.targets, controls=gate.controls, arg_value=gate.arg_value)
    for clbit, qubit in enumerate(reversed(read)):
        out.add_measurement("M", targets=[qubit], classical_store=clbit)
    return re.sub(r"^(measure [^;\\n]*)$", r"\\1;", circuit_to_qasm_str(out), flags=re.M)
'''
QUTIP_MAIN: Final = '''

if __name__ == "__main__":
    if sys.argv[1:2] == ["--qasm"]:
        names = sys.argv[2:] or list(JOBS)
        for name in names:
            build, read = JOBS[name]
            print(("" if len(names) == 1 else f"// {name}\\n") + to_qasm(build(), read), end="")
    else:
        for name, (build, read) in JOBS.items():
            print(f"{name}: QuTiP, run now, no noise  {top(shares_of(build(), read))}")
        print("Emulated on this computer: nothing was sent.")
'''

QRISP_IMPORTS: Final = "import sys\n"
QRISP_EXTRA_IMPORT: Final = "from pathlib import Path\n"
QRISP_HELP: Final = ("To send a circuit of your own without writing OpenQASM, write it in Qrisp as below. The first "
                     "line prints the OpenQASM 2 text of each circuit, as examples/qrisp/qasm2.py of the clone writes "
                     "it, and the second keeps that of one job:",
                     "    python emulate_qrisp.py --qasm\n    python emulate_qrisp.py --qasm JOB > mine.qasm")
QRISP_TO_QASM: Final = '''

def to_qasm(qc):
    """The OpenQASM 2 text of a circuit, by examples/qrisp/qasm2.py of the clone, which writes the Qrisp examples.

    Qrisp 0.9.10 writes OpenQASM through a package of another framework, so the examples use their own short converter.
    """
    examples = next(p for p in Path(__file__).resolve().parents if (p / "qrisp" / "qasm2.py").exists())
    sys.path.insert(0, str(examples / "qrisp"))
    from qasm2 import to_qasm2

    return to_qasm2(qc)
'''
QRISP_MAIN: Final = '''

if __name__ == "__main__":
    if sys.argv[1:2] == ["--qasm"]:
        names = sys.argv[2:] or list(JOBS)
        for name in names:
            print(("" if len(names) == 1 else f"// {name}\\n") + to_qasm(JOBS[name]()), end="")
    else:
        for name, build in JOBS.items():
            print(f"{name}: Qrisp's emulator, run now, no noise  {top(shares_of(build()))}")
        print("Emulated on this computer: nothing was sent.")
'''
