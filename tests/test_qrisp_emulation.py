"""Qrisp's emulator beside ours: the stored results, how far they differ and why. Only the last test needs Qrisp."""

import ast
import json
import platform
import sys
from math import log10
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
sys.path.insert(0, str(EXAMPLES / "hamiltonian"))
from circuit import circuit_of  # noqa: E402
from emulate import QRISP_FILE, Report, qrisp_stored, top  # noqa: E402
from example_folder import ExampleFolder  # noqa: E402
from folders import READMES  # noqa: E402
from overview import Overview, example_folders, largest_apart  # noqa: E402
from reading import Run  # noqa: E402

FOLDERS = Overview.of(EXAMPLES).folders
JOBS = [(folder, job) for folder in FOLDERS
        for job in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"]]
IDS = [f"{folder.name}-{job['name']}" for folder, job in JOBS]

# The largest difference measured is 0.0000088, in qrisp/ising. Qrisp rounds to 5 places, so up to 0.000005, and it then
# scales the shares; there the rounded shares sum to 1.00004, which moves its top share of 0.13 by 0.000005 more.
APART: float = 0.00001
STORED_PLACES: float = 1e-8                    # the stored shares hold 8 places


def end_steps(shares: dict) -> dict:
    """What qrisp/simulator/simulator.py does at the end of a run, on our shares: round to 5 places or 6, and scale."""
    places = int(-log10(max(shares.values()))) + 5
    rounded = {key: round(share, places) for key, share in shares.items()}
    return {key: share / sum(rounded.values()) for key, share in rounded.items() if share}


@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_each_job_has_a_stored_result_within_the_tolerance_of_ours(folder, job):
    stored = qrisp_stored(folder)[job["name"]]
    assert sum(stored.values()) == pytest.approx(1, abs=1e-6)
    assert largest_apart(circuit_of(folder / job["file"]).shares(), stored) <= APART


@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_the_end_steps_of_qrisp_alone_explain_the_difference(folder, job):
    """Our shares, with Qrisp's rounding and scaling, give Qrisp's: no share here is under its cut of 0.00001."""
    ours = circuit_of(folder / job["file"]).shares()
    assert min(ours.values()) > 0.00001
    assert largest_apart(end_steps(ours), qrisp_stored(folder)[job["name"]]) <= STORED_PLACES


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda f: f.name)
def test_each_file_holds_the_jobs_of_its_folder_and_the_version_of_qrisp_and_no_date(folder):
    held = json.loads((folder / QRISP_FILE).read_text(encoding="utf-8"))
    jobs = [job["name"] for job in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"]]
    assert set(held) == {"qrisp", "jobs"} and list(held["jobs"]) == jobs
    assert all(part.isdigit() for part in held["qrisp"].split("."))


def test_the_report_has_the_line_of_qrisp_between_the_perfect_machine_and_the_machine():
    lines = Report(EXAMPLES / "qrisp" / "grover3" / "manifest.json").lines()
    assert lines[1].startswith("  a perfect machine") and lines[4].startswith("  the machine, once")
    assert lines[2] == "  Qrisp's emulator, stored, no noise  110: 1.000"
    assert lines[3] == "  QuTiP, stored, no noise  110: 1.000"


def test_noise_leaves_the_line_of_qrisp_as_it_is():
    plain = Report(EXAMPLES / "hamiltonian" / "live" / "manifest.json").lines()[2]
    noisy = Report(EXAMPLES / "hamiltonian" / "live" / "manifest.json", shots=100, noise=0.1, readout=0.1).lines()
    assert noisy[2] == plain and "no noise" in plain and "with noise" in noisy[4]


def test_a_folder_with_no_stored_result_gives_no_line(tmp_path):
    (tmp_path / "BELL.qasm").write_bytes((EXAMPLES / "qrisp" / "bell" / "BELL.qasm").read_bytes())
    (tmp_path / "manifest.json").write_text('{"jobs": [{"name": "BELL", "file": "BELL.qasm", "shots": 1}]}')
    assert not any("Qrisp" in line for line in Report(tmp_path / "manifest.json").lines())


def test_the_standard_library_path_does_not_import_qrisp():
    for name in ("emulate", "circuit", "gates", "texts", "overview"):
        tree = ast.parse((EXAMPLES / "tools" / f"{name}.py").read_text(encoding="utf-8"))
        names = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        names += [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any(found.startswith("qrisp") for found in names), name


def test_the_table_has_a_cell_for_the_difference_in_each_row():
    overview = Overview.of(EXAMPLES)
    assert all(row.apart is not None and row.apart <= APART for row in overview.rows)
    assert "vs Qrisp" in overview.table().splitlines()[0]
    assert max(overview.rows, key=lambda row: row.apart).job == "ISING"


def test_the_tutorial_helper_prints_the_key_of_each_of_the_eleven_jobs():
    folder = EXAMPLES / "hamiltonian" / "state_transfer"
    run = Run.of(str(folder))
    lines = run.beside_qrisp(qrisp_stored(folder)).splitlines()
    assert len(lines) == 12 and lines[0].split() == ["job", "key", "ours", "Qrisp", "machine"]
    assert lines[1].split() == ["CONTROL", "001", "1.000000", "1.000000", "0.970"]
    main = next(line for line in lines if line.startswith("MAIN")).split()
    assert main[1] == "100" and main[4] == "0.641" and abs(float(main[2]) - float(main[3])) < APART


@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_the_two_lines_of_a_report_print_equal_shares_in_the_same_order(folder, job):
    """Float noise in our shares must not read as a difference between the two emulators."""
    assert top(circuit_of(folder / job["file"]).shares()) == top(qrisp_stored(folder)[job["name"]])


def test_the_folders_are_found_with_no_stored_file_read(tmp_path):
    """A broken stored file must not stop the command that makes it again."""
    (tmp_path / "manifest.json").write_text("{}", encoding="utf-8")
    (tmp_path / QRISP_FILE).write_text("{", encoding="utf-8")
    assert example_folders(tmp_path) == (tmp_path,)


def test_a_writer_leaves_the_stored_file_in_place(tmp_path):
    (tmp_path / QRISP_FILE).write_text("{}", encoding="utf-8")
    ExampleFolder(tmp_path, "euroqexa-bell").write_page(READMES["euroqexa-bell"])
    assert (tmp_path / QRISP_FILE).read_text(encoding="utf-8") == "{}"
    assert QRISP_FILE in (tmp_path / "README.md").read_text(encoding="utf-8")


def rebuilt_text(folder: Path) -> str:
    """The file of a folder, made again now."""
    pytest.importorskip("qrisp")
    from write_qrisp_emulated import stored_text

    return stored_text(folder)


@pytest.mark.parametrize("folder", FOLDERS, ids=lambda f: f.name)
def test_a_run_of_qrisp_gives_each_stored_file(folder):
    """Byte for byte where the files were made; elsewhere within one unit of Qrisp's rounding."""
    rebuilt = rebuilt_text(folder)
    if (sys.platform, platform.machine()) == ("darwin", "arm64"):
        assert rebuilt.encode("utf-8") == (folder / QRISP_FILE).read_bytes()
    else:
        held = qrisp_stored(folder)
        for name, said in json.loads(rebuilt)["jobs"].items():
            assert said == pytest.approx(held[name], abs=0.00002)
