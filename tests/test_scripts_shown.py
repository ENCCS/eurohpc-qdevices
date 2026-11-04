"""Choose one in all_examples.ipynb: the first job of each script of a folder, and the run of each script.

No test here runs a script: a stand-in takes the place of runpy.run_path. The QuTiP job of qrisp/hello, on 25 qubits,
takes about 25 seconds and 1.5 GB, so the page must leave it to a terminal however NAME spells the folder.
"""

import importlib.util
import json
import runpy
import shutil
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from scripts_shown import LINES, SCRIPTS, first_job, show_scripts  # noqa: E402

HELLO = ["qrisp/hello", "qrisp/hello/", "./qrisp/hello", "qrisp//hello", str(EXAMPLES / "qrisp" / "hello")]
WIDE_LINE = "A job on 25 qubits: run it in a terminal, with `python emulate_qutip.py` in its folder."


def script_with(tmp_path, gates):
    """A script whose first job has a def line, `gates` lines and a return, with a function after it."""
    lines = ['"""A script."""', "", "", "def one():", *(f"    qc.h({n})" for n in range(gates)), "    return qc",
             "", "", "def top():", "    pass"]
    path = tmp_path / "emulate_qutip.py"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path, lines


def test_a_short_job_shows_whole_under_a_line_that_names_the_script(tmp_path):
    path, lines = script_with(tmp_path, 3)
    assert first_job(path) == (f"The first job in {path.as_posix()}, a file of {len(lines)} lines:\n\n"
                               + "\n".join(lines[3:8]))


def test_a_long_job_shows_its_first_lines_and_then_dots(tmp_path):
    path, lines = script_with(tmp_path, 30)
    shown = first_job(path).splitlines()[2:]
    assert shown == [*lines[3:3 + LINES], "    ..."]
    assert first_job(path, most=32).splitlines()[2:] == lines[3:35]


@pytest.mark.parametrize("spelling", HELLO[:4])
def test_the_line_above_a_job_names_the_folder_with_no_doubled_slash(spelling, monkeypatch):
    monkeypatch.chdir(EXAMPLES)
    text = first_job(Path(spelling) / "emulate_qutip.py")
    assert text.startswith("The first job in qrisp/hello/emulate_qutip.py, a file of ") and "//" not in text


@pytest.mark.parametrize("spelling", HELLO, ids=["plain", "slash-after", "dot-first", "two-slashes", "absolute"])
def test_the_qutip_job_on_25_qubits_is_left_to_a_terminal_however_the_folder_is_spelt(spelling, monkeypatch, capsys):
    pytest.importorskip("qutip_qip")
    ran = []

    def stand_in(path, run_name=None):
        assert not path.endswith("emulate_qutip.py"), f"the QuTiP job of {path} ran"
        ran.append(Path(path).name)

    monkeypatch.chdir(EXAMPLES)
    monkeypatch.setattr(runpy, "run_path", stand_in)
    show_scripts(Path(spelling))
    assert WIDE_LINE in capsys.readouterr().out
    assert ran == (["emulate_qrisp.py"] if importlib.util.find_spec("qrisp") else [])


def test_the_width_is_read_from_the_script_that_runs_not_from_the_texts(tmp_path, monkeypatch, capsys):
    """qrisp/hello with a narrower text, its scripts not written again yet: its QuTiP script is still wide."""
    pytest.importorskip("qutip_qip")
    for name in ("manifest.json", "emulate_qutip.py", "emulate_qrisp.py"):
        shutil.copy(EXAMPLES / "qrisp" / "hello" / name, tmp_path / name)
    (tmp_path / "HELLO.qasm").write_text('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\n', encoding="utf-8")
    ran = []
    monkeypatch.setattr(runpy, "run_path", lambda path, run_name=None: ran.append(Path(path).name))
    show_scripts(tmp_path)
    assert WIDE_LINE in capsys.readouterr().out and "emulate_qutip.py" not in ran


def test_the_page_says_how_many_lines_it_shows_and_leaves_the_cost_of_the_wide_job_to_its_readme():
    cells = json.loads((EXAMPLES / "all_examples.ipynb").read_text(encoding="utf-8"))["cells"]
    text = "".join(next(cell for cell in cells if cell.get("id") == "cell-6")["source"])
    assert f"up to {LINES} lines" in text and "25 seconds" not in text
    assert "runs on 25 qubits, so the cell does not run it: its `README.md` says what it takes" in text


def test_a_folder_whose_scripts_are_not_written_yet_says_so_and_runs_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runpy, "run_path", lambda path, run_name=None: pytest.fail(f"{path} ran"))
    show_scripts(tmp_path)
    out = capsys.readouterr().out
    assert [f"{(tmp_path / script).as_posix()} is not written yet" in out for script, _, _ in SCRIPTS] == [True, True]


def test_a_narrower_folder_runs_each_script_whose_package_is_here(monkeypatch, capsys):
    ran = []
    monkeypatch.chdir(EXAMPLES)
    monkeypatch.setattr(runpy, "run_path", lambda path, run_name=None: ran.append(Path(path).name))
    show_scripts(Path("qrisp/grover3"))
    out = capsys.readouterr().out
    here = [script for script, module, _ in SCRIPTS if importlib.util.find_spec(module)]
    assert ran == here and "A job on" not in out
    assert out.count("is not installed here: its stored line above holds what it gives.") == len(SCRIPTS) - len(here)
