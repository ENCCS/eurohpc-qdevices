"""Write emulate_qutip.py, the example in QuTiP code, in each example folder or in those named: `qutip-scripts`.

The gates come from `gate_steps` of qutip_emulator.py, as the emulator runs them, so each script gives the shares that
qutip_emulated.json stores. It makes no network call and runs no circuit.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import fill
from typing import Final

from circuit import circuit_of
from emulate import jobs_of
from overview import write_stored
from qutip_emulator import PLACES, WHY, Step, gate_steps
from readme import KERNEL_FIRST, WIDE
from script_parts import TOP, angle_text, commented, example_path, function_of, keys_of, main_block, main_imports
from script_qasm import QUTIP_EXTRA_IMPORT, QUTIP_HELP, QUTIP_IMPORTS, QUTIP_QASM, QUTIP_TO_QASM, for_qasm

EXAMPLES: Final = Path(__file__).resolve().parent.parent
SCRIPT: Final = "emulate_qutip.py"
# The names a script binds or looks up when it runs: no job function takes them.
TAKEN: Final = {"np", "basis", "QubitCircuit", "JOBS", "shares_of", "top", "re", "os", "sys", "circuit_to_qasm_str",
                "to_qasm"}
IMPORTS: Final = "import numpy as np\nfrom qutip import basis\nfrom qutip_qip.circuit import QubitCircuit\n"
SHARES: Final = '''

def shares_of(qc, read):
    """Run a circuit from |0...0> and give the share of each key above 1e-12; `read` lists the qubits of a key."""
    final = qc.run(basis([2] * qc.N, [0] * qc.N))
    probability = np.abs(final.full().reshape([2] * qc.N)) ** 2                # one axis per qubit, qubit 0 first
    probability = probability.sum(axis=tuple(q for q in range(qc.N) if q not in read))     # over the qubits not read
    by_key = probability.transpose([sorted(read).index(q) for q in read]).reshape(-1)     # the axes in key order
    return {format(index, f"0{len(read)}b"): float(by_key[index]) for index in np.flatnonzero(by_key > 1e-12)}
'''
LOOP: Final = '''for name, (build, read) in JOBS.items():
    print(f"{name}: QuTiP, run now, no noise  {top(shares_of(build(), read))}")
print("Emulated on this computer: nothing was sent.")
'''


def arg_text(arg) -> str:
    """The angle or angles of a gate, as code."""
    if isinstance(arg, (list, tuple)):
        inner = ", ".join(angle_text(a) for a in arg)
        return f"[{inner}]" if isinstance(arg, list) else f"({inner})"
    return angle_text(arg)


def gate_line(step: Step) -> str:
    """One gate as one line of code, with the gate of the text after it where qutip-qip names it otherwise."""
    parts = [f'"{step.gate}"', *([f"controls={list(step.controls)}"] if step.controls else []),
             f"targets={list(step.targets)}", *([f"arg_value={arg_text(step.arg)}"] if step.arg is not None else [])]
    return f"qc.add_gate({', '.join(parts)})" + (f"  # {step.ours}" if step.ours in WHY else "")


def _and(words: list) -> str:
    return " and ".join(", ".join(words).rsplit(", ", 1))


def renumbered(qubits: tuple) -> str:
    """Which qubit here is which qubit of the text, where they differ; nothing if none does."""
    moved = [(new, old) for new, old in enumerate(qubits) if new != old]
    if not moved:
        return ""
    many = len(moved) > 1
    return (f"; {'qubits' if many else 'qubit'} {_and([str(new) for new, _ in moved])} here {'are' if many else 'is'} "
            f"{_and([f'q[{old}]' for _, old in moved])} of the text")


def head(path: str, keys: str, wide: str, qasm: bool) -> str:
    """The module docstring and the imports of a script."""
    return '"""' + "\n\n".join([
        f"The example {path} in QuTiP code: each job gate by gate in qutip-qip, run with no noise.",
        fill("Run it where QuTiP and qutip-qip are installed. In a terminal on Binder, from File > New > Terminal, "
             "which starts at the top of the clone:", 120),
        f"    cd examples/{path} && python emulate_qutip.py",
        "From the top of a clone of your own, with pixi:",
        f"    pixi run --manifest-path examples/qrisp/pixi.toml python examples/{path}/emulate_qutip.py",
        fill(f"It prints the share of each key of each job in the form of emulate.sh: {keys}. The shares are those "
             f"that qutip_emulated.json stores, to {PLACES} places.{wide}", 120),
        *([fill(QUTIP_HELP[0], 120), QUTIP_HELP[1]] if qasm else []),
        fill("examples/tools/write_qutip_scripts.py writes this file from the text of each job. It needs nothing else "
             "from the clone, so you can copy it anywhere.", 120)]) + '\n"""\n\n' + (
        main_imports(QUTIP_IMPORTS if qasm else "") + "\n" + IMPORTS + (QUTIP_EXTRA_IMPORT if qasm else ""))


@dataclass
class Script:
    """The script of one folder; `explained` holds each gate of the text whose comment line is written."""

    folder: Path
    path: str
    explained: set = field(default_factory=set)
    defined: dict = field(default_factory=dict)

    def job(self, name: str, file: str) -> str:
        """The function that builds the circuit of one job, one line per gate."""
        function, circuit = function_of(name, TAKEN, self.defined), circuit_of(self.folder / file)
        size = len(circuit.qubits)
        about = f"The job {name}: {file}, on {size} qubit{'' if size == 1 else 's'}{renumbered(circuit.qubits)}."
        return "\n".join([f"def {function}():", f'    """{about}"""', f"    qc = QubitCircuit({size})",
                          *commented(gate_steps(circuit), WHY, self.explained, gate_line), "    return qc\n"])

    def _wide(self, jobs: list) -> str:
        sizes = {job["name"]: len(circuit_of(self.folder / job["file"]).qubits) for job in jobs}
        wide = "".join(f" The job {name} runs on {size} qubits, a state of 2**{size} amplitudes: it takes "
                       f"{WIDE[size]}." for name, size in sizes.items() if size in WIDE)
        return f"{wide} {KERNEL_FIRST}" if wide else ""

    def text(self) -> str:
        """The whole script."""
        jobs = jobs_of(self.folder)
        body = "".join(f"\n{self.job(job['name'], job['file'])}\n" for job in jobs)
        rows = "".join(f'    "{job["name"]}": ({self.defined[job["name"]]}, '
                       f"{list(circuit_of(self.folder / job['file']).renumbered().bits)}),\n" for job in jobs)
        qasm = for_qasm(self.folder)
        tail = SHARES + TOP + (QUTIP_TO_QASM if qasm else "") + main_block(self.folder, SCRIPT, LOOP, QUTIP_QASM)
        return (head(self.path, keys_of(jobs), self._wide(jobs), qasm) + "\n" + body
                + "\n# Each job: the function that builds its circuit, and the qubit that each character of a key "
                  "reads, in order.\nJOBS = {\n" + rows + "}\n" + tail)


def script_text(folder: Path, root: Path = EXAMPLES) -> str:
    """The emulate_qutip.py of one folder below `root`."""
    return Script(folder, example_path(folder, root)).text()


def write_scripts(root: Path, folders: list) -> None:
    """Write emulate_qutip.py in each of `folders`, or in every example folder below `root`."""
    write_stored(root, SCRIPT, lambda folder: script_text(folder, root), folders)


if __name__ == "__main__":
    write_scripts(EXAMPLES, [Path(a).resolve() for a in sys.argv[1:]])
