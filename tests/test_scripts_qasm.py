"""The --qasm of each Euro-Q-Exa script: the OpenQASM 2 text that QuTiP and Qrisp code give, read back and compared.

The texts are read by the parser of the examples and must give the shares of the text that was sent. Qrisp's, through
examples/qrisp/qasm2.py, gives the same bytes as the text sent, but where a gate of the text was built from others.
"""

import json
import runpy
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from circuit import Circuit, circuit_of  # noqa: E402
from emulate import jobs_of  # noqa: E402
from overview import example_folders, largest_apart  # noqa: E402

FOLDERS = [f for f in example_folders(EXAMPLES)
           if json.loads((f / "manifest.json").read_text(encoding="utf-8"))["site"] == "euroqexa"]
JOBS = [(folder, job) for folder in FOLDERS for job in jobs_of(folder)]
IDS = [f"{folder.relative_to(EXAMPLES).as_posix()}-{job['name']}" for folder, job in JOBS]
# The gates of the original qelib1.inc, which Euro-Q-Exa takes, and the two built into OpenQASM 2.
QELIB1 = {"u3", "u2", "u1", "cx", "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cz", "cy", "ch",
          "ccx", "crz", "cu1", "cu3", "U", "CX"}
BUILT = {("euroqexa-inverse", "INVERSE")}          # its crz is written as rz and cx, as Qrisp has no crz method


def gates_of(text: str) -> set:
    """The name of each gate a text applies."""
    skip = ("//", "OPENQASM", "include", "qreg", "creg", "measure", "gate ")
    return {line.split()[0].split("(")[0] for line in text.splitlines() if line.strip() and not line.startswith(skip)}


def test_only_the_euroqexa_folders_have_a_qasm_part():
    assert len(FOLDERS) == 24
    for folder in example_folders(EXAMPLES):
        assert ("def to_qasm" in (folder / "emulate_qutip.py").read_text(encoding="utf-8")) == (folder in FOLDERS)
        assert ("def to_qasm" in (folder / "emulate_qrisp.py").read_text(encoding="utf-8")) == (folder in FOLDERS)


@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_qutips_text_reads_back_to_the_shares_of_the_text_sent_with_gates_of_qelib1(folder, job):
    pytest.importorskip("qutip_qip")
    script = runpy.run_path(str(folder / "emulate_qutip.py"))
    build, read = script["JOBS"][job["name"]]
    text = script["to_qasm"](build(), read)
    assert gates_of(text) <= QELIB1, gates_of(text) - QELIB1
    assert all(line.endswith(";") for line in text.splitlines() if line.startswith("measure"))
    assert largest_apart(Circuit.of_text(text).shares(), circuit_of(folder / job["file"]).shares()) < 1e-9


@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_qrisps_text_is_the_text_sent_but_where_a_gate_was_built_from_others(folder, job):
    pytest.importorskip("qrisp")
    script = runpy.run_path(str(folder / "emulate_qrisp.py"))
    text, sent = script["to_qasm"](script["JOBS"][job["name"]]()), (folder / job["file"]).read_text(encoding="utf-8")
    assert (text == sent) != ((folder.relative_to(EXAMPLES).as_posix(), job["name"]) in BUILT)
    assert largest_apart(Circuit.of_text(text).shares(), circuit_of(folder / job["file"]).shares()) < 1e-9
