"""Write emulate_qutip.py, the example in QuTiP code, in each example folder or in those named: `qutip-scripts`.

The gates come from `gate_steps` of qutip_emulator.py, as the emulator runs them, so each script gives the shares that
qutip_emulated.json stores. It makes no network call and runs no circuit.
"""

import keyword
import sys
from dataclasses import dataclass, field
from math import gcd, pi
from pathlib import Path
from textwrap import fill
from typing import Final

from circuit import circuit_of
from emulate import jobs_of
from overview import write_stored
from qutip_emulator import WHY, Step, gate_steps

EXAMPLES: Final = Path(__file__).resolve().parent.parent
SCRIPT: Final = "emulate_qutip.py"
TAKEN: Final = {"np", "basis", "QubitCircuit", "JOBS", "shares_of", "top"}       # no job function takes these names
WIDE: Final = {25: "about 25 seconds and 1.1 GB of memory on a laptop"}         # measured: 23 s, 1.09 GB at most
KEYS: Final = {"broker": "a key reads qubit 0 first, as the broker gives it",
               "text": "the first character of a key is the highest classical bit, as on the site"}
IMPORTS: Final = "import numpy as np\nfrom qutip import basis\nfrom qutip_qip.circuit import QubitCircuit\n"
TAIL: Final = '''

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
'''


def angle_text(value: float) -> str:
    """An angle as code: a fraction of pi where it is one to the last bit, else the decimal of the same float."""
    for down in (1, 2, 3, 4, 6, 8, 12, 16, 32, 64):
        for up in (k for k in range(1, 4 * down) if gcd(k, down) == 1):
            if abs(value) == up * pi / down:
                sign, times, over = "-" if value < 0 else "", "" if up == 1 else f"{up} * ", f" / {down}"
                return f"{sign}{times}np.pi{over if down > 1 else ''}"
    return repr(float(value))


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


def head(path: str, keys: str, wide: str) -> str:
    """The module docstring and the imports of a script."""
    return '"""' + "\n\n".join([
        f"The example {path} in QuTiP code: each job gate by gate in qutip-qip, run with no noise.",
        "Run it where QuTiP and qutip-qip are installed. In a terminal on Binder, which starts at the top of the "
        "clone:",
        f"    cd examples/{path} && python emulate_qutip.py",
        "From the top of a clone of your own, with pixi:",
        f"    pixi run --manifest-path examples/qrisp/pixi.toml python examples/{path}/emulate_qutip.py",
        fill(f"It prints the share of each key of each job in the form of emulate.sh: {keys}. The shares are those "
             f"that qutip_emulated.json stores, to 8 places.{wide}", 120),
        fill("examples/tools/write_qutip_scripts.py writes this file from the text of each job. It needs nothing else "
             "from the clone, so you can copy it anywhere.", 120)]) + '\n"""\n\n' + IMPORTS


@dataclass
class Script:
    """The script of one folder; `explained` holds each gate of the text whose comment line is written."""

    folder: Path
    path: str
    explained: set = field(default_factory=set)

    def _steps(self, steps: tuple) -> list:
        lines = []
        for step in steps:
            if step.ours in WHY and step.ours not in self.explained:
                self.explained.add(step.ours)
                lines.append(f"    # {step.ours}: {WHY[step.ours]}")
            lines.append(f"    {gate_line(step)}")
        return lines

    def job(self, name: str, file: str) -> str:
        """The function that builds the circuit of one job, one line per gate."""
        function, circuit = name.lower(), circuit_of(self.folder / file)
        if not function.isidentifier() or keyword.iskeyword(function) or function in TAKEN:
            raise ValueError(f"a job name that is not a free Python name: {name}")
        size = len(circuit.qubits)
        about = f"The job {name}: {file}, on {size} qubit{'' if size == 1 else 's'}{renumbered(circuit.qubits)}."
        return "\n".join([f"def {function}():", f'    """{about}"""', f"    qc = QubitCircuit({size})",
                          *self._steps(gate_steps(circuit)), "    return qc\n"])

    def _wide(self, jobs: list) -> str:
        sizes = {job["name"]: len(circuit_of(self.folder / job["file"]).qubits) for job in jobs}
        return "".join(f" The job {name} runs on {size} qubits, a state of 2**{size} amplitudes: it takes "
                       f"{WIDE[size]}." for name, size in sizes.items() if size in WIDE)

    def text(self) -> str:
        """The whole script."""
        jobs = jobs_of(self.folder)
        keys = KEYS["broker" if all(job["file"].endswith(".json") for job in jobs) else "text"]
        rows = "".join(f'    "{job["name"]}": ({job["name"].lower()}, '
                       f"{list(circuit_of(self.folder / job['file']).renumbered().bits)}),\n" for job in jobs)
        return (head(self.path, keys, self._wide(jobs)) + "\n"
                + "".join(f"\n{self.job(job['name'], job['file'])}\n" for job in jobs)
                + "\n# Each job: the function that builds its circuit, and the qubit that each character of a key "
                  "reads, in order.\nJOBS = {\n" + rows + "}\n" + TAIL)


def script_text(folder: Path, root: Path = EXAMPLES) -> str:
    """The emulate_qutip.py of one folder below `root`."""
    return Script(folder, folder.relative_to(root).as_posix()).text()


def write_scripts(root: Path, folders: list) -> None:
    """Write emulate_qutip.py in each of `folders`, or in every example folder below `root`."""
    write_stored(root, SCRIPT, lambda folder: script_text(folder, root), folders)


if __name__ == "__main__":
    write_scripts(EXAMPLES, [Path(a).resolve() for a in sys.argv[1:]])
