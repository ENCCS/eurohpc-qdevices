"""Each folder's emulate_qrisp.py: the example in Qrisp code, to read and to run, and the stored shares it gives.

The first tests read the scripts and need no Qrisp. Those that run a script need Qrisp.
"""

import ast
import json
import platform
import runpy
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from emulate import jobs_of, qrisp_stored, top  # noqa: E402
from overview import example_folders, largest_apart  # noqa: E402

SCRIPT = "emulate_qrisp.py"
FOLDERS = example_folders(EXAMPLES)
IDS = [folder.relative_to(EXAMPLES).as_posix() for folder in FOLDERS]
TOOLS = {path.stem for path in (EXAMPLES / "tools").glob("*.py")}
# The stored file holds 8 places; on another kind of computer Qrisp's own rounding can move a share by about 0.00001.
APART = 1e-8 if (sys.platform, platform.machine()) == ("darwin", "arm64") else 0.0001


def for_qasm(folder: Path) -> bool:
    """A folder for Euro-Q-Exa: its script also writes OpenQASM 2."""
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["site"] == "euroqexa"


def tree(folder: Path) -> ast.Module:
    """The script of a folder, parsed."""
    return ast.parse((folder / SCRIPT).read_text(encoding="utf-8"))


def imported(module: ast.Module) -> set:
    """The top name of each module a script imports."""
    names = {alias.name for node in ast.walk(module) if isinstance(node, ast.Import) for alias in node.names}
    names |= {node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom)}
    return {name.split(".")[0] for name in names}


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_a_script_imports_only_qrisp_and_the_standard_library_and_nothing_from_tools(folder):
    found = imported(tree(folder))
    assert found <= {"qrisp", "contextlib", "io", "math", "sys", "pathlib", "qasm2"}, found
    assert ("qasm2" in found) == for_qasm(folder)
    assert not found & TOOLS


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_a_script_has_one_function_for_each_job_of_its_manifest(folder):
    functions = {node.name for node in tree(folder).body if isinstance(node, ast.FunctionDef)}
    helpers = {"shares_of", "top"} | ({"to_qasm"} if for_qasm(folder) else set())
    assert {job["name"].lower() for job in jobs_of(folder)} | helpers == functions


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_each_readme_names_the_script_with_the_path_of_its_folder(folder):
    path, page = folder.relative_to(EXAMPLES).as_posix(), (folder / "README.md").read_text(encoding="utf-8")
    assert f"`cd examples/{path} && python {SCRIPT}`" in page
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


# ------------------------------------------------------------ with Qrisp


@pytest.mark.parametrize("folder", FOLDERS, ids=IDS)
def test_each_script_gives_the_stored_shares_of_every_job(folder):
    pytest.importorskip("qrisp")
    script, stored = runpy.run_path(str(folder / SCRIPT)), qrisp_stored(folder)
    for job in jobs_of(folder):
        said = script["shares_of"](script["JOBS"][job["name"]]())
        assert largest_apart(said, stored[job["name"]]) <= APART, job["name"]


def test_a_script_run_as_a_program_prints_a_line_for_each_job_as_emulate_sh_does(capsys):
    pytest.importorskip("qrisp")
    folder = EXAMPLES / "qrisp" / "bell"
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
