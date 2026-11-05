"""The part of emulate_qutip.py and emulate_qrisp.py that writes OpenQASM 2, for the folders of Euro-Q-Exa alone.

Euro-Q-Exa takes OpenQASM 2 and compiles it. VLQ takes OpenQASM 3 in its own gates and Piast-Q the broker's list of
operations, so their scripts have no such part: on --qasm they stop and say what their site takes. The two writers of
the scripts add these texts as they are, and main_block of script_parts.py puts the --qasm branch and the usage line of
a folder, by qasm_branch and usage, in the main block.
"""

import json
from pathlib import Path
from typing import Final

SITE: Final = "euroqexa"
# What each other site takes in place of OpenQASM 2, for the stop of --qasm in its folders.
INSTEAD: Final = {"vlq": "VLQ takes OpenQASM 3 in its own gates r, cz and move",
                  "piastq": "Piast-Q takes the broker's list of RZ, R and RXX"}

QUTIP_IMPORTS: Final = "import re\n"
QUTIP_EXTRA_IMPORT: Final = "from qutip_qip.qasm import circuit_to_qasm_str\n"
QUTIP_HELP: Final = ("To send a circuit of your own without writing OpenQASM, write it in QuTiP as below. The first "
                     "line prints the OpenQASM 2 text that qutip-qip writes from each circuit, and the second keeps "
                     "that of one job:",
                     "    python emulate_qutip.py --qasm\n    python emulate_qutip.py --qasm JOB > mine.qasm")
QUTIP_TO_QASM: Final = '''

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
    text = re.sub(r"^(measure [^;\\n]*)$", r"\\1;", circuit_to_qasm_str(out), flags=re.M)
    return re.sub(r"(?<![\\w.])(\\d+)(e[-+]?\\d+)", r"\\1.0\\2", text)
'''
# The start of the --qasm branch of both scripts: the jobs named, else all, and a stop at a name that is not a job.
JOB_NAMES: Final = '''names = args[1:] or list(JOBS)
if unknown := [name for name in names if name not in JOBS]:
    sys.exit(f"no job {', '.join(unknown)} here; the jobs: {', '.join(JOBS)}")
'''
QUTIP_QASM: Final = JOB_NAMES + '''for name in names:
    build, read = JOBS[name]
    print(("" if len(names) == 1 else f"// {name}\\n") + to_qasm(build(), read), end="")
'''

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
    examples = next((p for p in Path(__file__).resolve().parents if (p / "qrisp" / "qasm2.py").exists()), None)
    if examples is None:
        sys.exit("--qasm needs examples/qrisp/qasm2.py: run this file in its folder of a clone")
    sys.path.insert(0, str(examples / "qrisp"))
    from qasm2 import to_qasm2

    return to_qasm2(qc)
'''
QRISP_QASM: Final = JOB_NAMES + '''for name in names:
    print(("" if len(names) == 1 else f"// {name}\\n") + to_qasm(JOBS[name]()), end="")
'''


def site_of(folder: Path) -> str:
    """The site of a folder, as its manifest names it."""
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["site"]


def for_qasm(folder: Path) -> bool:
    """Whether a folder is for Euro-Q-Exa, so that its scripts also write OpenQASM 2."""
    return site_of(folder) == SITE


def qasm_branch(folder: Path, writes: str) -> str:
    """The body of the --qasm branch: `writes` in a folder of Euro-Q-Exa, else a stop that says what the site takes."""
    if for_qasm(folder):
        return writes
    return f'sys.exit("--qasm is for the folders of Euro-Q-Exa; {INSTEAD[site_of(folder)]}")\n'


def usage(folder: Path, script: str) -> str:
    """The one-line usage of a script: --qasm and the names of jobs in a folder of Euro-Q-Exa alone."""
    return f"python {script}" + (" [--qasm [JOB ...]]" if for_qasm(folder) else "")
