"""Write emulate_qrisp.py, the example in Qrisp code, in each example folder or in those named: `qrisp-scripts`.

The calls come from `qrisp_calls` of qrisp_emulator.py, as the emulator runs them, so each script gives the shares that
qrisp_emulated.json stores. It makes no network call and runs no circuit.
"""

import json
import keyword
import re
import sys
from pathlib import Path
from textwrap import fill
from typing import Final

from circuit import circuit_of
from emulate import jobs_of
from overview import write_stored
from qrisp_emulator import WHY, Call, measures, qrisp_calls
from write_qutip_scripts import KEYS, angle_text

EXAMPLES: Final = Path(__file__).resolve().parent.parent
SCRIPT: Final = "emulate_qrisp.py"
TAKEN: Final = {"pi", "QuantumCircuit", "JOBS", "shares_of", "top", "StringIO", "redirect_stdout", "redirect_stderr"}
IMPORTS: Final = "from contextlib import redirect_stderr, redirect_stdout\nfrom io import StringIO\n"
TAIL: Final = '''

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
'''


def call_line(call: Call) -> str:
    """One Qrisp call as one line of code, angles first, then qubits."""
    args = ", ".join(angle_text(a).replace("np.pi", "pi") if isinstance(a, float) else str(a) for a in call.args)
    return f"qc.{call.method}({args})" + (f"  # {call.ours}" if call.ours in WHY else "")


def head(path: str, keys: str, made: str) -> str:
    """The module docstring of a script."""
    return '"""' + "\n\n".join([
        f"The example {path} in Qrisp code: each job gate by gate, on Qrisp's own emulator, with no noise.",
        "Run it where Qrisp is installed. In a terminal on Binder, which starts at the top of the clone:",
        f"    cd examples/{path} && python emulate_qrisp.py",
        "From the top of a clone of your own, with pixi:",
        f"    pixi run --manifest-path examples/qrisp/pixi.toml python examples/{path}/emulate_qrisp.py",
        fill(f"It prints the share of each key of each job in the form of emulate.sh: {keys}. The shares are those "
             "that qrisp_emulated.json stores, to 8 places, on the kind of computer that made it; Qrisp rounds its "
             "own shares to 5 or 6 places, so another kind of computer can differ by about 0.00001.", 120),
        *([fill(made, 120)] if made else []),
        fill("examples/tools/write_qrisp_scripts.py writes this file from the text of each job, with the same calls "
             "as the emulator of the examples. It needs nothing else from the clone, so you can copy it anywhere.",
             120)]) + '\n"""\n\n'


class Script:
    """The script of one folder; `explained` holds each gate of the text whose comment line is written."""

    def __init__(self, folder: Path, path: str):
        self.folder, self.path, self.explained = folder, path, set()

    def _calls(self, calls: tuple) -> list:
        lines = []
        for call in calls:
            if call.ours in WHY and call.ours not in self.explained:
                self.explained.add(call.ours)
                lines.append(f"    # {call.ours}: {WHY[call.ours]}")
            lines.append(f"    {call_line(call)}")
        return lines

    def job(self, name: str, file: str) -> str:
        """The function that builds the circuit of one job: one line per call, then the measurements."""
        function, circuit = name.lower(), circuit_of(self.folder / file)
        if not function.isidentifier() or keyword.iskeyword(function) or function in TAKEN:
            raise ValueError(f"a job name that is not a free Python name: {name}")
        size, bits = max(circuit.qubits) + 1, len(circuit.bits)
        return "\n".join([
            f"def {function}():", f'    """The job {name}: {file}, on {size} qubit{"" if size == 1 else "s"}."""',
            f"    qc = QuantumCircuit({size}, {bits})", *self._calls(qrisp_calls(circuit)),
            "    # the measurements, qubit then classical bit: bit 0 is the last character of a key",
            *(f"    qc.measure({qubit}, {clbit})" for qubit, clbit in measures(circuit)), "    return qc\n"])

    def _made(self) -> str:
        made = json.loads((self.folder / "manifest.json").read_text(encoding="utf-8")).get("made_with", "")
        if not made.startswith("Qrisp"):
            return ""
        program = " Its Qrisp program is in examples/qrisp/programs.py." if self.path.startswith("qrisp/") else ""
        return f"Its text was made with {made}.{program}"

    def text(self) -> str:
        """The whole script."""
        jobs = jobs_of(self.folder)
        keys = KEYS["broker" if all(job["file"].endswith(".json") for job in jobs) else "text"]
        body = "".join(f"\n{self.job(job['name'], job['file'])}\n" for job in jobs)
        imports = IMPORTS + ("from math import pi\n" if re.search(r"\bpi\b", body) else "")
        imports += "\nfrom qrisp import QuantumCircuit\n"
        rows = "".join(f'    "{job["name"]}": {job["name"].lower()},\n' for job in jobs)
        return (head(self.path, keys, self._made()) + imports + "\n" + body
                + "\n# Each job and the function that builds its circuit.\nJOBS = {\n" + rows + "}\n" + TAIL)


def script_text(folder: Path, root: Path = EXAMPLES) -> str:
    """The emulate_qrisp.py of one folder below `root`."""
    return Script(folder, folder.relative_to(root).as_posix()).text()


if __name__ == "__main__":
    write_stored(EXAMPLES, SCRIPT, script_text, [Path(a).resolve() for a in sys.argv[1:]])
