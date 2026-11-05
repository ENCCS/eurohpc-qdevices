"""Each folder's emulate_qrisp.py: the example in Qrisp code, to read and to run, and the stored shares it gives.

The first tests read the scripts and need no Qrisp. Those that run a script need Qrisp.
"""

import ast
import importlib
import json
import platform
import re
import runpy
import shutil
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from circuit import circuit_of  # noqa: E402
from emulate import jobs_of, qrisp_stored, top  # noqa: E402
from gates import ONE, TWO  # noqa: E402
from overview import example_folders, largest_apart  # noqa: E402
from script_qasm import for_qasm  # noqa: E402

SCRIPT = "emulate_qrisp.py"
FOLDERS = example_folders(EXAMPLES)
IDS = [folder.relative_to(EXAMPLES).as_posix() for folder in FOLDERS]
# The stored file holds 8 places; on another kind of computer Qrisp's own rounding can move a share by about 0.00001.
APART = 1e-8 if (sys.platform, platform.machine()) == ("darwin", "arm64") else 0.0001
EVERY_GATE = ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[5];\ncreg c[3];\nh q[0];\nx q[1];\ny q[2];\nz q[0];\n'
              "s q[1];\nsdg q[2];\nt q[0];\ntdg q[1];\nrx(0.7) q[2];\nry(0.4) q[0];\nrz(1.1) q[1];\n"
              "u3(0.7,0.3,1.1) q[2];\nr(0.6,1.0) q[4];\ncx q[0],q[1];\ncy q[1],q[2];\ncz q[2],q[4];\n"
              "crz(0.9) q[4],q[0];\nrxx(0.8) q[1],q[2];\nmove q[2],q[4];\nmeasure q[4] -> c[0];\n"
              "measure q[0] -> c[1];\nmeasure q[1] -> c[2];\n")


def tree(folder: Path) -> ast.Module:
    """The script of a folder, parsed."""
    return ast.parse((folder / SCRIPT).read_text(encoding="utf-8"))


def imported(module: ast.Module) -> set:
    """The top name of each module a script imports."""
    names = {alias.name for node in ast.walk(module) if isinstance(node, ast.Import) for alias in node.names}
    names |= {node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom)}
    return {name.split(".")[0] for name in names}


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_a_script_imports_only_qrisp_and_the_standard_library_and_qasm2_for_euroqexa(folder):
    found = imported(tree(folder))
    assert found <= {"qrisp", "contextlib", "io", "math", "os", "sys", "pathlib", "qasm2"}, found
    assert ("qasm2" in found) == for_qasm(folder)


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_a_script_has_one_function_for_each_job_of_its_manifest(folder):
    module, jobs = tree(folder), jobs_of(folder)
    functions = [node.name for node in module.body if isinstance(node, ast.FunctionDef)]
    helpers = ["shares_of", "top"] + (["to_qasm"] if for_qasm(folder) else [])
    assert functions == [job["name"].lower() for job in jobs] + helpers
    table = next(node.value for node in module.body if isinstance(node, ast.Assign) and node.targets[0].id == "JOBS")
    assert [key.value for key in table.keys] == [job["name"] for job in jobs]
    assert [value.id for value in table.values] == [job["name"].lower() for job in jobs]


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_each_readme_names_the_script_with_the_path_of_its_folder(folder):
    path, page = folder.relative_to(EXAMPLES).as_posix(), (folder / "README.md").read_text(encoding="utf-8")
    assert "Run in this folder, each prints what its emulator gives" in page
    assert f"`python {SCRIPT}` where Qrisp is, as on Binder." in page
    assert f"examples/{path}/emulate_qutip.py`, and the same with `{SCRIPT}`" in page
    assert f"| `{SCRIPT}` |" in page


def test_the_task_and_the_top_readmes_name_the_writer():
    assert 'qrisp-scripts = { cmd = "python examples/tools/write_qrisp_scripts.py"' in (
        EXAMPLES / "qrisp" / "pixi.toml").read_text(encoding="utf-8")
    assert f"| `{SCRIPT}` |" in (EXAMPLES / "README.md").read_text(encoding="utf-8")
    assert "qrisp-scripts" in (EXAMPLES / "tools" / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_beside_the_gate_lines_a_script_keeps_the_size_limits_of_the_code(folder):
    for node in (node for node in tree(folder).body if isinstance(node, ast.FunctionDef)):
        calls = sum(isinstance(line, ast.Expr) and isinstance(line.value, ast.Call) for line in node.body)
        assert node.end_lineno - node.lineno + 1 - calls <= 25, node.name
    lines = (folder / SCRIPT).read_text(encoding="utf-8").splitlines()
    assert len(lines) - sum(line.lstrip().startswith(("qc.", "# ")) for line in lines) <= 200


# ------------------------------------------------------------ with Qrisp


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_each_script_gives_the_stored_shares_of_every_job(folder):
    pytest.importorskip("qrisp")
    script, stored = runpy.run_path(str(folder / SCRIPT)), qrisp_stored(folder)
    for job in jobs_of(folder):
        said = script["shares_of"](script["JOBS"][job["name"]]())
        assert largest_apart(said, stored[job["name"]]) <= APART, job["name"]


def test_a_script_run_as_a_program_prints_a_line_for_each_job_as_emulate_sh_does(monkeypatch, capsys):
    pytest.importorskip("qrisp")
    folder = EXAMPLES / "qrisp" / "bell"
    monkeypatch.setattr(sys, "argv", [str(folder / SCRIPT)])                       # python emulate_qrisp.py
    monkeypatch.setattr(sys, "orig_argv", [sys.executable, str(folder / SCRIPT)])
    runpy.run_path(str(folder / SCRIPT), run_name="__main__")
    stored = qrisp_stored(folder)
    assert capsys.readouterr().out.splitlines() == [
        f"{name}: Qrisp's emulator, run now, no noise  {top(stored[name])}" for name in stored] + [
        "Emulated on this computer: nothing was sent."]


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_the_writer_gives_the_same_bytes_again(folder):
    pytest.importorskip("qrisp")
    from write_qrisp_scripts import script_text

    assert script_text(folder) == (folder / SCRIPT).read_text(encoding="utf-8")


@pytest.mark.parametrize("writer", ["write_qutip_scripts", "write_qrisp_scripts"])
def test_both_writers_stop_with_one_line_at_a_folder_outside_examples(writer, tmp_path):
    """A folder as `qrisp-examples --out my-runs` writes one: a manifest and its text, but not below examples/."""
    pytest.importorskip("qutip_qip" if writer == "write_qutip_scripts" else "qrisp")
    folder = tmp_path / "my-runs" / "bell"
    folder.mkdir(parents=True)
    for name in ("manifest.json", "BELL.qasm"):
        shutil.copy(EXAMPLES / "qrisp" / "bell" / name, folder / name)
    said = f"{folder}: emulate_qutip.py and emulate_qrisp.py are written in the example folders below examples/ only"
    with pytest.raises(SystemExit, match=f"^{re.escape(said)}$"):
        importlib.import_module(writer).script_text(folder, tmp_path / "examples")


@pytest.mark.parametrize("writer", ["write_qutip_scripts", "write_qrisp_scripts"])
def test_no_job_function_takes_a_name_that_a_script_imports(writer):
    """A job named OS would give def os(), which would hide the module os from the main block."""
    pytest.importorskip("qutip_qip" if writer == "write_qutip_scripts" else "qrisp")
    module = importlib.import_module(writer)
    bound = {(alias.asname or alias.name).split(".")[0] for folder in FOLDERS
             for node in ast.parse(module.script_text(folder)).body if isinstance(node, (ast.Import, ast.ImportFrom))
             for alias in node.names}
    assert bound <= module.TAKEN, bound - module.TAKEN


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_the_emulator_and_the_scripts_make_the_same_calls(folder):
    """Each job of a script makes the emulator's calls and measurements, one for one; no circuit is run."""
    pytest.importorskip("qrisp")
    from qrisp_emulator import qrisp_circuit

    def calls(qc):
        return [(i.op.name, list(i.op.params), [qc.qubits.index(q) for q in i.qubits],
                 [qc.clbits.index(c) for c in i.clbits]) for i in qc.data]

    script = runpy.run_path(str(folder / SCRIPT))
    for job in jobs_of(folder):
        made = qrisp_circuit(circuit_of(folder / job["file"]))
        assert calls(script["JOBS"][job["name"]]()) == calls(made), job["name"]


def every_gate_script(tmp_path: Path, writer) -> tuple:
    """A folder whose one job uses every gate of gates.py, its script by `writer`, run; and our shares of the job."""
    folder = tmp_path / "examples" / "every"
    folder.mkdir(parents=True)
    (folder / "EVERY.qasm").write_text(EVERY_GATE, encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps({"format": "qdevices/1", "site": "vlq", "jobs": [
        {"order": 1, "name": "EVERY", "file": "EVERY.qasm", "shots": 1}]}), encoding="utf-8")
    circuit = circuit_of(folder / "EVERY.qasm")
    assert {name for name, _, _ in circuit.ops} == set(ONE) | set(TWO)
    (folder / "script.py").write_text(writer(folder, tmp_path / "examples"), encoding="utf-8")
    return runpy.run_path(str(folder / "script.py")), circuit.shares()


def test_a_script_of_every_gate_gives_our_shares(tmp_path):
    pytest.importorskip("qrisp")
    from write_qrisp_scripts import script_text

    script, ours = every_gate_script(tmp_path, script_text)
    assert largest_apart(script["shares_of"](script["JOBS"]["EVERY"]()), ours) <= 0.0001
    assert "pi" not in script                          # no call uses pi: the comment line of r names it, no import


@pytest.mark.parametrize(("made", "said"), [
    ("a small function, examples/hamiltonian/write_chain.py",
     "Its text was made with a small function, examples/hamiltonian/write_chain.py."),
    ("Qrisp and a small function, examples/hamiltonian/write_chain.py",
     "Its text was made with Qrisp and a small function, examples/hamiltonian/write_chain.py."),
    (None, None)], ids=["chain-alone", "with-qrisp", "none"])
def test_a_script_says_what_made_its_text_as_the_manifest_says_with_qrisp_or_not(made, said, tmp_path):
    """hamiltonian/live: its one text comes from chain.py alone, and the made_with of its manifest says so."""
    pytest.importorskip("qrisp")
    from write_qrisp_scripts import script_text

    folder, copy = EXAMPLES / "hamiltonian" / "live", tmp_path / "examples" / "hamiltonian" / "live"
    copy.mkdir(parents=True)
    shutil.copy(folder / "MAIN.qasm", copy / "MAIN.qasm")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    manifest = {key: value for key, value in {**manifest, "made_with": made}.items() if value is not None}
    (copy / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    doc = " ".join(ast.get_docstring(ast.parse(script_text(copy, tmp_path / "examples"))).split())
    assert (said in doc) if said else ("made with" not in doc)
