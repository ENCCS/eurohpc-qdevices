"""Write emulate_qrisp.py, the example in Qrisp code, in each example folder or in those named: `qrisp-scripts`.

The calls come from `qrisp_calls` of qrisp_emulator.py, as the emulator runs them, so each script gives the shares that
qrisp_emulated.json stores. It makes no network call and runs no circuit.
"""

import json
import re
import sys
from pathlib import Path
from textwrap import fill
from typing import Final

from circuit import circuit_of
from emulate import jobs_of
from overview import write_stored
from qrisp_emulator import PLACES, WHY, Call, measures, qrisp_calls
from script_parts import MAIN_IMPORT, TOP, angle_text, commented, example_path, function_of, keys_of, main_block
from script_qasm import QRISP_EXTRA_IMPORT, QRISP_HELP, QRISP_QASM, QRISP_TO_QASM, for_qasm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "qrisp"))
from programs import source_of

EXAMPLES: Final = Path(__file__).resolve().parent.parent
SCRIPT: Final = "emulate_qrisp.py"
# The names a script binds or looks up when it runs: no job function takes them.
TAKEN: Final = {"pi", "QuantumCircuit", "JOBS", "shares_of", "top", "StringIO", "redirect_stdout", "redirect_stderr",
                "os", "sys", "Path", "to_qasm"}
IMPORTS: Final = MAIN_IMPORT + "from contextlib import redirect_stderr, redirect_stdout\nfrom io import StringIO\n"
SHARES: Final = '''

def shares_of(qc):
    """Run a circuit on Qrisp's emulator, with no progress bar, and give the share of each key."""
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return {key: float(share) for key, share in qc.run().items()}
'''
LOOP: Final = '''for name, build in JOBS.items():
    print(f"{name}: Qrisp's emulator, run now, no noise  {top(shares_of(build()))}")
print("Emulated on this computer: nothing was sent.")
'''


def call_line(call: Call) -> str:
    """One Qrisp call as one line of code, angles first, then qubits."""
    args = ", ".join(angle_text(a).replace("np.pi", "pi") if isinstance(a, float) else str(a) for a in call.args)
    return f"qc.{call.method}({args})" + (f"  # {call.ours}" if call.ours in WHY else "")


def head(path: str, keys: str, made: str, qasm: bool) -> str:
    """The module docstring of a script."""
    return '"""' + "\n\n".join([
        f"The example {path} in Qrisp code: each job gate by gate, on Qrisp's own emulator, with no noise.",
        fill("Run it where Qrisp is installed. In a terminal on Binder, from File > New > Terminal, which starts at "
             "the top of the clone:", 120),
        f"    cd examples/{path} && python emulate_qrisp.py",
        "From the top of a clone of your own, with pixi:",
        f"    pixi run --manifest-path examples/qrisp/pixi.toml python examples/{path}/emulate_qrisp.py",
        fill(f"It prints the share of each key of each job in the form of emulate.sh: {keys}. The shares are those "
             f"that qrisp_emulated.json stores, to {PLACES} places, on the kind of computer that made it; Qrisp "
             "rounds its own shares to 5 or 6 places, so another kind of computer can differ by about 0.00001.", 120),
        *([fill(made, 120)] if made else []),
        *([fill(QRISP_HELP[0], 120), QRISP_HELP[1]] if qasm else []),
        fill("examples/tools/write_qrisp_scripts.py writes this file from the text of each job, with the same calls "
             "as the emulator of the examples. It needs nothing else from the clone"
             + (", but --qasm, which uses examples/qrisp/qasm2.py." if qasm else ", so you can copy it anywhere."),
             120)]) + '\n"""\n\n'


class Script:
    """The script of one folder; `explained` holds each gate of the text whose comment line is written."""

    def __init__(self, folder: Path, path: str):
        self.folder, self.path, self.explained, self.defined = folder, path, set(), {}

    def job(self, name: str, file: str) -> str:
        """The function that builds the circuit of one job: one line per call, then the measurements."""
        function, circuit = function_of(name, TAKEN, self.defined), circuit_of(self.folder / file)
        size, bits = max(circuit.qubits) + 1, len(circuit.bits)
        return "\n".join([
            f"def {function}():", f'    """The job {name}: {file}, on {size} qubit{"" if size == 1 else "s"}."""',
            f"    qc = QuantumCircuit({size}, {bits})",
            *commented(qrisp_calls(circuit), WHY, self.explained, call_line),
            "    # the measurements, qubit then classical bit: bit 0 is the last character of a key",
            *(f"    qc.measure({qubit}, {clbit})" for qubit, clbit in measures(circuit)), "    return qc\n"])

    def _made(self) -> str:
        manifest = json.loads((self.folder / "manifest.json").read_text(encoding="utf-8"))
        if not (made := manifest.get("made_with", "")):
            return ""
        texts = "Its texts were" if len({job["file"] for job in manifest["jobs"]}) > 1 else "Its text was"
        if not self.path.startswith("qrisp/"):
            return f"{texts} made with {made}."
        function, file = source_of(self.path.removeprefix("qrisp/"))
        return f"{texts} made with {made}. Its Qrisp program is the function {function} of examples/qrisp/{file}."

    def text(self) -> str:
        """The whole script."""
        jobs = jobs_of(self.folder)
        body = "".join(f"\n{self.job(job['name'], job['file'])}\n" for job in jobs)
        qasm = for_qasm(self.folder)
        uses_pi = re.search(r"^    qc\..*\bpi\b", body, re.M)                  # in a call, not in a comment
        imports = IMPORTS + ("from math import pi\n" if uses_pi else "")
        imports += (QRISP_EXTRA_IMPORT if qasm else "") + "\nfrom qrisp import QuantumCircuit\n"
        tail = SHARES + TOP + (QRISP_TO_QASM if qasm else "") + main_block(self.folder, SCRIPT, LOOP, QRISP_QASM)
        rows = "".join(f'    "{job["name"]}": {self.defined[job["name"]]},\n' for job in jobs)
        return (head(self.path, keys_of(jobs), self._made(), qasm) + imports + "\n" + body
                + "\n# Each job and the function that builds its circuit.\nJOBS = {\n" + rows + "}\n" + tail)


def script_text(folder: Path, root: Path = EXAMPLES) -> str:
    """The emulate_qrisp.py of one folder below `root`."""
    return Script(folder, example_path(folder, root)).text()


if __name__ == "__main__":
    write_stored(EXAMPLES, SCRIPT, script_text, [Path(a).resolve() for a in sys.argv[1:]])
