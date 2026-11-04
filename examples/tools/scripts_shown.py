"""For Choose one in all_examples.ipynb: the first job of a folder's two scripts, and what each prints when run.

The two scripts are emulate_qutip.py, in QuTiP code, and emulate_qrisp.py, in Qrisp code.
"""

import ast
import importlib.util
import re
import runpy
from pathlib import Path
from typing import Final

SCRIPTS: Final = (("emulate_qutip.py", "qutip_qip", "QuTiP"), ("emulate_qrisp.py", "qrisp", "Qrisp"))
LINES: Final = 20                # the most lines of a job shown
WIDE: Final = 20                 # qubits: a QuTiP job on so many or more is left to a terminal


def first_job(path: Path, most: int = LINES) -> str:
    """The first job function of a script, whole up to `most` lines, under a line that names the script."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    job = next(node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef))
    body = lines[job.lineno - 1:job.end_lineno]
    shown = body if len(body) <= most else [*body[:most], "    ..."]
    return f"The first job in {path.as_posix()}, a file of {len(lines)} lines:\n\n" + "\n".join(shown)


def widest(folder: Path) -> int:
    """The most qubits of a job of the folder: the N of QubitCircuit(N) in its emulate_qutip.py, the file that runs."""
    text = (folder / "emulate_qutip.py").read_text(encoding="utf-8")
    return max(int(n) for n in re.findall(r"QubitCircuit\((\d+)\)", text))


def show_scripts(folder: Path) -> None:
    """For QuTiP, then Qrisp: the first job of its script, and what the script prints, run here if it may be."""
    for script, module, name in SCRIPTS:
        path = folder / script
        if not path.exists():
            print(f"\n{path.as_posix()} is not written yet: examples/README.md says how, under After a change.")
            continue
        print(f"\n{first_job(path)}\n")
        if importlib.util.find_spec(module) is None:
            print(f"{name} is not installed here: its stored line above holds what it gives.")
        elif name == "QuTiP" and (wide := widest(folder)) >= WIDE:
            print(f"A job on {wide} qubits: run it in a terminal, with `python {script}` in its folder.")
        else:
            runpy.run_path(str(path), run_name="__main__")
