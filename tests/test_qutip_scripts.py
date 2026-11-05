"""Each folder's emulate_qutip.py: the example in QuTiP code, to read and to run, and the stored shares it gives.

The first tests read the scripts and need no QuTiP. Those that run a script need qutip-qip. A job on 25 qubits takes
about 25 seconds and 1.5 GB, so it runs only with QUTIP_WIDE=1 in the environment: the repository registers no pytest
marks, and the test of the path through QuTiP leaves that job out too.
"""

import ast
import os
import runpy
import shutil
import sys
from math import pi
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from circuit import circuit_of  # noqa: E402
from emulate import jobs_of, qutip_stored, top  # noqa: E402
from overview import example_folders, largest_apart  # noqa: E402
from script_parts import angle_text, function_of  # noqa: E402
from script_qasm import for_qasm  # noqa: E402
from scripts_shown import WIDE, widest  # noqa: E402

SCRIPT = "emulate_qutip.py"
FOLDERS = example_folders(EXAMPLES)
IDS = [folder.relative_to(EXAMPLES).as_posix() for folder in FOLDERS]
HELPERS = ["shares_of", "top"]
APART = 1e-8                     # the stored file holds 8 places


def tree(folder: Path) -> ast.Module:
    """The script of a folder, parsed."""
    return ast.parse((folder / SCRIPT).read_text(encoding="utf-8"))


def imported(module: ast.Module) -> set:
    """The top name of each module a script imports."""
    names = {alias.name for node in ast.walk(module) if isinstance(node, ast.Import) for alias in node.names}
    names |= {node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom)}
    return {name.split(".")[0] for name in names}


def run(folder: Path) -> dict:
    """The script of a folder run as a module, with no main, when its jobs are not too wide for this run."""
    pytest.importorskip("qutip_qip")
    if widest(folder) >= WIDE and not os.environ.get("QUTIP_WIDE"):
        pytest.skip("a job on 25 qubits: about 25 seconds and 1.5 GB; set QUTIP_WIDE=1 to run it")
    return runpy.run_path(str(folder / SCRIPT))


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_a_script_imports_only_numpy_qutip_and_qutip_qip_and_nothing_from_tools(folder):
    found = imported(tree(folder))
    assert found == {"numpy", "qutip", "qutip_qip", "os", "sys"} | ({"re"} if for_qasm(folder) else set())


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_a_script_has_one_function_per_job_and_one_line_per_gate_of_its_text(folder):
    jobs = jobs_of(folder)
    functions = {node.name: node for node in tree(folder).body if isinstance(node, ast.FunctionDef)}
    assert list(functions) == [job["name"].lower() for job in jobs] + HELPERS + (
        ["to_qasm"] if for_qasm(folder) else [])
    table = next(node.value for node in tree(folder).body if isinstance(node, ast.Assign)
                 and node.targets[0].id == "JOBS")
    assert [key.value for key in table.keys] == [job["name"] for job in jobs]
    assert [value.elts[0].id for value in table.values] == [job["name"].lower() for job in jobs]
    for job in jobs:
        calls = [node for node in ast.walk(functions[job["name"].lower()]) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute) and node.func.attr == "add_gate"]
        assert len(calls) == len(circuit_of(folder / job["file"]).ops), job["name"]


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_each_readme_names_the_script_with_the_path_of_its_folder(folder):
    path, page = folder.relative_to(EXAMPLES).as_posix(), (folder / "README.md").read_text(encoding="utf-8")
    assert "Run in this folder, each prints what its emulator gives" in page
    assert f"`python {SCRIPT}` where QuTiP and qutip-qip are installed" in page
    assert f"`pixi run --manifest-path examples/qrisp/pixi.toml python examples/{path}/{SCRIPT}`" in page
    assert f"| `{SCRIPT}` |" in page


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_a_readme_names_no_qrisp_writer_on_the_qutip_line(folder):
    page = (folder / "README.md").read_text(encoding="utf-8")
    assert "write_qrisp_emulated.py" not in page and "qrisp-emulated" not in page


def test_the_page_above_says_how_to_make_the_files_of_one_folder_again():
    """The five tasks, in their order: the pictures last, as they draw from the stored files."""
    page, tasks = (EXAMPLES / "README.md").read_text("utf-8"), (EXAMPLES / "qrisp" / "pixi.toml").read_text("utf-8")
    order = ("qutip-emulated", "qrisp-emulated", "qutip-scripts", "qrisp-scripts", "pictures")
    run = "pixi run --manifest-path examples/qrisp/pixi.toml"
    assert "".join(f"{run} {task} examples/qrisp/bell\n" for task in order) in page
    assert all(f'\n{task} = {{ cmd = "python examples/tools/write_' in tasks for task in order)
    assert f"| `{SCRIPT}` |" in page and "qutip-scripts" in (EXAMPLES / "tools" / "README.md").read_text("utf-8")
    assert 'qutip-scripts = { cmd = "python examples/tools/write_qutip_scripts.py"' in tasks


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_beside_the_gate_lines_a_script_keeps_the_size_limits_of_the_code(folder):
    """test_sizes.py leaves the scripts out: here each part but the gate lines stays within 25 lines."""
    module = tree(folder)
    for node in (node for node in module.body if isinstance(node, ast.FunctionDef)):
        gates = sum(isinstance(line, ast.Expr) and isinstance(line.value, ast.Call) for line in node.body)
        assert node.end_lineno - node.lineno + 1 - gates <= 25, node.name
    lines = (folder / SCRIPT).read_text(encoding="utf-8").splitlines()
    assert len(lines) - sum(line.lstrip().startswith(("qc.add_gate(", "# ")) for line in lines) <= 200


def test_only_the_job_on_25_qubits_is_wide():
    assert [folder.relative_to(EXAMPLES).as_posix() for folder in FOLDERS if widest(folder) >= WIDE] == ["qrisp/hello"]
    assert "about 25 seconds and 1.5 GB" in (EXAMPLES / "qrisp" / "hello" / SCRIPT).read_text(encoding="utf-8")
    assert f"Here `{SCRIPT}` runs a job on 25 qubits: it takes about 25 seconds and 1.5 GB" in (
        EXAMPLES / "qrisp" / "hello" / "README.md").read_text(encoding="utf-8")


def test_the_script_of_the_wide_job_says_to_shut_the_kernel_down_first_on_binder(tmp_path):
    """The docstrings of qrisp/hello and qrisp/bell as the writer writes them now; the README gives the numbers."""
    pytest.importorskip("qutip_qip")
    from readme import KERNEL_FIRST
    from write_qutip_scripts import script_text

    said = {}
    for name in ("hello", "bell"):
        folder, copy = EXAMPLES / "qrisp" / name, tmp_path / "examples" / "qrisp" / name
        copy.mkdir(parents=True)
        for file in ("manifest.json", *(job["file"] for job in jobs_of(folder))):
            shutil.copy(folder / file, copy / file)
        said[name] = " ".join(ast.get_docstring(ast.parse(script_text(copy, tmp_path / "examples"))).split())
    assert f"it takes about 25 seconds and 1.5 GB of memory on a laptop. {KERNEL_FIRST}" in said["hello"]
    assert not any(c.isdigit() for c in KERNEL_FIRST) and KERNEL_FIRST not in said["bell"]


@pytest.mark.parametrize(("names", "taken"), [(["CLASS"], set()), (["PRINT"], set()), (["1BELL"], set()),
                                              (["__FILE__"], set()), (["TOP"], {"top"}), (["BELL", "Bell"], set())],
                         ids=["keyword", "builtin", "not-a-name", "two-underscores", "taken", "twice"])
def test_a_job_name_that_is_not_a_free_python_name_stops_the_writers(names, taken):
    """Only the last name is refused: in "twice", BELL is the function bell, which Bell would take again."""
    defined = {}
    for name in names[:-1]:
        function_of(name, taken, defined)
    with pytest.raises(ValueError, match="not a free Python name"):
        function_of(names[-1], taken, defined)


# ------------------------------------------------------------ with qutip-qip


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_each_script_gives_the_stored_shares_of_every_job(folder):
    script, stored = run(folder), qutip_stored(folder)
    for job in jobs_of(folder):
        build, read = script["JOBS"][job["name"]]
        said = script["shares_of"](build(), read)
        assert largest_apart(said, stored[job["name"]]) <= APART, job["name"]
        assert script["top"](said) == top(stored[job["name"]]) == top(said), job["name"]


def test_a_script_run_as_a_program_prints_a_line_for_each_job_as_emulate_sh_does(monkeypatch, capsys):
    pytest.importorskip("qutip_qip")
    folder = EXAMPLES / "hamiltonian" / "state_transfer"
    monkeypatch.setattr(sys, "argv", [str(folder / SCRIPT)])                       # python emulate_qutip.py
    monkeypatch.setattr(sys, "orig_argv", [sys.executable, str(folder / SCRIPT)])
    runpy.run_path(str(folder / SCRIPT), run_name="__main__")
    lines = capsys.readouterr().out.splitlines()
    stored = qutip_stored(folder)
    assert lines == [f"{name}: QuTiP, run now, no noise  {top(stored[name])}" for name in stored] + [
        "Emulated on this computer: nothing was sent."]
    assert lines[1] == "MAIN: QuTiP, run now, no noise  100: 0.970  001: 0.027  010: 0.003"


def test_the_writer_gives_the_same_bytes_again(tmp_path):
    pytest.importorskip("qutip_qip")
    from write_qutip_scripts import write_scripts

    copies = []
    for folder in FOLDERS:
        copy = tmp_path / "examples" / folder.relative_to(EXAMPLES)
        copy.mkdir(parents=True)
        for name in ["manifest.json", *(job["file"] for job in jobs_of(folder))]:
            shutil.copy(folder / name, copy / name)
        copies.append(copy)
    write_scripts(tmp_path / "examples", copies)
    for folder, copy in zip(FOLDERS, copies, strict=True):
        assert (copy / SCRIPT).read_bytes() == (folder / SCRIPT).read_bytes(), folder.name


def test_an_angle_is_written_as_the_same_float():
    """Read back by the reader of the texts, which takes pi and the same operations in the same order."""
    from texts import angle

    written = {value: angle_text(value) for value in (pi / 2, -pi / 4, 3 * pi / 4, -3 * pi / 8, 2 * pi, pi, 0.0,
                                                      0.7, -1.2345678901234567, 0.1 + 0.2)}
    assert written[pi / 2] == "np.pi / 2" and written[-3 * pi / 8] == "-3 * np.pi / 8" and written[0.7] == "0.7"
    assert all(angle(text.replace("np.pi", "pi")) == value for value, text in written.items())


def test_a_script_cuts_the_shares_where_the_emulator_does():
    pytest.importorskip("qutip_qip")
    from qutip_emulator import SMALLEST
    from write_qutip_scripts import SHARES

    assert SHARES.count(f"> {SMALLEST:g}") == 1 and f"above {SMALLEST:g}" in SHARES


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_the_emulator_and_the_scripts_take_the_gates_from_one_place(folder):
    """Each job of a script has the emulator's gates, one for one, and reads the same qubits; no circuit is run."""
    pytest.importorskip("qutip_qip")
    from qutip_emulator import qutip_circuit

    def gates(qc):
        return [(gate.name, gate.targets, gate.controls or [], gate.arg_value) for gate in qc.gates]

    script = runpy.run_path(str(folder / SCRIPT))
    for job in jobs_of(folder):
        circuit, (build, read) = circuit_of(folder / job["file"]), script["JOBS"][job["name"]]
        assert gates(build()) == gates(qutip_circuit(circuit)), job["name"]
        assert read == list(circuit.renumbered().bits), job["name"]


def test_each_step_keeps_the_gate_of_the_text():
    pytest.importorskip("qutip_qip")
    from qutip_emulator import gate_steps

    steps = gate_steps(circuit_of(EXAMPLES / "vlq-bell" / "BELL.qasm"))
    assert [step.ours for step in steps] == ["r", "r", "move", "cz", "move", "r"]


def test_a_script_of_every_gate_gives_our_shares(tmp_path):
    pytest.importorskip("qutip_qip")
    from test_qrisp_scripts import every_gate_script
    from write_qutip_scripts import script_text

    script, ours = every_gate_script(tmp_path, script_text)
    build, read = script["JOBS"]["EVERY"]
    assert largest_apart(script["shares_of"](build(), read), ours) <= 1e-12
