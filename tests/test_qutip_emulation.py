"""QuTiP's stored results beside ours: every folder holds them, every job is there, and they agree. No QuTiP needed."""

import ast
import json
import re
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
sys.path.insert(0, str(EXAMPLES / "hamiltonian"))
from circuit import circuit_of  # noqa: E402
from emulate import QUTIP_FILE, Report, came_back, jobs_of, qrisp_stored, qutip_stored, top  # noqa: E402
from example_folder import ExampleFolder  # noqa: E402
from folders import READMES  # noqa: E402
from overview import Overview, example_folders, largest_apart  # noqa: E402
from reading import Run  # noqa: E402

FOLDERS = example_folders(EXAMPLES)
JOBS = [(folder, job) for folder in FOLDERS
        for job in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"]]
IDS = [f"{folder.relative_to(EXAMPLES).as_posix()}-{job['name']}" for folder, job in JOBS]

# The largest difference measured is 0.0000000050, in qrisp/qubo: the stored shares hold 8 places, so up to 0.000000005.
# Before that rounding, QuTiP and ours differ by at most 0.0000000000000014, in qrisp/ising2.
APART: float = 1e-8


def held(folder: Path) -> dict:
    """The whole stored file of a folder."""
    return json.loads((folder / QUTIP_FILE).read_text(encoding="utf-8"))


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda f: f.relative_to(EXAMPLES).as_posix())
def test_each_folder_holds_the_file_with_the_versions_and_each_job_run_or_named_as_not_run(folder):
    stored = held(folder)
    jobs = [job["name"] for job in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"]]
    assert list(stored) == ["qutip", "qutip_qip", "jobs", "not_run"]
    assert not set(stored["jobs"]) & set(stored["not_run"])
    assert [name for name in jobs if name in stored["jobs"] or name in stored["not_run"]] == jobs
    assert all(isinstance(why, str) and why for why in stored["not_run"].values())


def test_the_versions_are_the_ones_the_workspace_pins_and_every_job_ran():
    pins = (EXAMPLES / "qrisp" / "pixi.toml").read_text(encoding="utf-8")
    for folder in FOLDERS:
        stored = held(folder)
        assert re.search(rf'^qutip = "=={re.escape(stored["qutip"])}"$', pins, re.MULTILINE)
        assert re.search(rf'^qutip-qip = "=={re.escape(stored["qutip_qip"])}"$', pins, re.MULTILINE)
        assert stored["not_run"] == {}, folder


@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_each_job_on_qutip_agrees_with_ours_and_reads_the_same_in_a_report(folder, job):
    stored, ours = qutip_stored(folder)[job["name"]], circuit_of(folder / job["file"]).shares()
    assert sum(stored.values()) == pytest.approx(1, abs=1e-6)
    assert largest_apart(ours, stored) <= APART
    assert top(ours) == top(stored)


def test_the_report_has_the_line_of_qutip_after_the_line_of_qrisp():
    lines = Report(EXAMPLES / "qrisp" / "grover3" / "manifest.json").lines()
    assert lines[2].startswith("  Qrisp's emulator, stored") and lines[4].startswith("  the machine, once")
    assert lines[3] == "  QuTiP, stored, no noise  110: 1.000"


def test_noise_leaves_the_line_of_qutip_as_it_is():
    plain = Report(EXAMPLES / "hamiltonian" / "live" / "manifest.json").lines()[3]
    noisy = Report(EXAMPLES / "hamiltonian" / "live" / "manifest.json", shots=100, noise=0.1, readout=0.1).lines()
    assert noisy[3] == plain and plain.startswith("  QuTiP, stored, no noise") and "with noise" in noisy[4]


def test_a_folder_with_no_stored_file_gives_no_line_of_qutip(tmp_path):
    (tmp_path / "BELL.qasm").write_bytes((EXAMPLES / "qrisp" / "bell" / "BELL.qasm").read_bytes())
    (tmp_path / "manifest.json").write_text('{"jobs": [{"name": "BELL", "file": "BELL.qasm", "shots": 1}]}')
    assert not any("QuTiP" in line for line in Report(tmp_path / "manifest.json").lines())


def test_the_standard_library_path_does_not_import_qutip_or_numpy():
    for name in ("emulate", "circuit", "gates", "texts", "overview", "palette"):
        tree = ast.parse((EXAMPLES / "tools" / f"{name}.py").read_text(encoding="utf-8"))
        names = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        names += [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any(found.startswith(("qutip", "numpy")) for found in names), name


def test_a_circuit_names_the_qubits_it_uses_and_renumbers_them_from_zero_in_order():
    circuit = circuit_of(EXAMPLES / "vlq-bell" / "BELL.qasm")
    assert circuit.qubits == (0, 1, 24)
    small = circuit.renumbered()
    assert small.qubits == (0, 1, 2) and small.bits == (1, 0) and small.shares() == circuit.shares()


def test_the_readers_of_a_folder_give_its_jobs_and_its_counts_and_nothing_for_a_job_not_sent():
    folder = EXAMPLES / "euroqexa-three-jobs"
    assert [job["name"] for job in jobs_of(folder)] == ["X", "BELL", "BELL_AGAIN"] and came_back(folder) == {}
    assert came_back(EXAMPLES / "qrisp" / "bell") == {"BELL": {"00": 54, "01": 2, "10": 3, "11": 41}}


def test_the_table_has_a_cell_for_the_difference_to_qutip_in_each_row():
    overview = Overview.of(EXAMPLES)
    assert all(row.qutip_apart is not None and row.qutip_apart <= APART for row in overview.rows)
    head = overview.table().splitlines()[0]
    assert head.index("vs Qrisp") < head.index("vs QuTiP") < head.index("read")


def test_the_tutorial_helper_prints_qutip_beside_qrisp_and_keeps_the_old_table():
    folder = EXAMPLES / "hamiltonian" / "state_transfer"
    run = Run.of(str(folder))
    lines = run.beside({"Qrisp": qrisp_stored(folder), "QuTiP": qutip_stored(folder)}).splitlines()
    assert len(lines) == 12 and lines[0].split() == ["job", "key", "ours", "Qrisp", "QuTiP", "machine"]
    assert lines[1].split() == ["CONTROL", "001", "1.000000", "1.000000", "1.000000", "0.970"]
    main = next(line for line in lines if line.startswith("MAIN")).split()
    assert main[1] == "100" and main[2] == main[4] == "0.970409" and main[5] == "0.641"
    assert run.beside({"Qrisp": qrisp_stored(folder)}) == run.beside_qrisp(qrisp_stored(folder))


def test_a_writer_leaves_the_stored_file_in_place_and_the_readme_names_it(tmp_path):
    (tmp_path / QUTIP_FILE).write_text("{}", encoding="utf-8")
    ExampleFolder(tmp_path, "euroqexa-bell").write_page(READMES["euroqexa-bell"])
    assert (tmp_path / QUTIP_FILE).read_text(encoding="utf-8") == "{}"
    assert f"`{QUTIP_FILE}`" in (tmp_path / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda f: f.relative_to(EXAMPLES).as_posix())
def test_each_readme_names_the_file_and_says_the_report_prints_it(folder):
    text = (folder / "README.md").read_text(encoding="utf-8")
    assert f"`{QUTIP_FILE}`" in text and "the stored results of Qrisp's emulator and of QuTiP" in text


def test_the_pages_above_say_how_to_make_the_files_again():
    task = "pixi run --manifest-path examples/qrisp/pixi.toml qutip-emulated"
    for page in (EXAMPLES / "README.md", EXAMPLES / "hamiltonian" / "README.md", EXAMPLES / "tools" / "README.md"):
        assert task in page.read_text(encoding="utf-8"), page.name
    assert re.search(r"^qutip-emulated = .*write_qutip_emulated\.py", (EXAMPLES / "qrisp" / "pixi.toml").read_text(
        encoding="utf-8"), re.MULTILINE)
