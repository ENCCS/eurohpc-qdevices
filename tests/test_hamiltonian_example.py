"""examples/hamiltonian: the model, the texts, the sends and the comparison; the last tests need Qrisp."""

import json
import os
import shutil
import subprocess
import sys
from math import pi, sqrt
from pathlib import Path

import pytest
from fakes import FakeSite, places_in, records_of, send

from qdevices import config, dryrun, runner
from qdevices.paths import Places
from qdevices.qasm import Qasm
from qdevices.runner import Refused
from qdevices.sites import SITES

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "examples" / "hamiltonian"
sys.path[:0] = [str(HERE), str(ROOT / "examples" / "tools")]
import compare  # noqa: E402
from chain import BONDS, SPINS, Steps, T, amplitudes, closed_form, control  # noqa: E402
from circuit import amplitudes_of, shares_of  # noqa: E402
from compare import Compared  # noqa: E402
from example_folder import KEPT  # noqa: E402
from hydrogen import MADE  # noqa: E402
from reading import Reading, Run, distance, load_counts  # noqa: E402

FOLDER = HERE / "state_transfer"
LIVE = HERE / "live"
MANIFEST = FOLDER / "manifest.json"
JOBS = json.loads(MANIFEST.read_text(encoding="utf-8"))["jobs"]
TOML = ROOT / "examples" / "qdevices.toml"
SIZES = {"CONTROL": (4, 0), "MAIN": (30, 10), "QRISP": (62, 20), "REPEAT": (30, 10), "HALF": (30, 10),
         "BACK": (46, 18), "ZERO": (29, 10), "STEPS1": (22, 6), "STEPS4": (46, 18), "STEPS8": (78, 34),
         "ORDER1": (26, 8)}
ARRIVALS = {"STEPS1": 0.508, "MAIN": 0.970, "STEPS4": 0.998, "STEPS8": 1.000, "ORDER1": 0.759}
READINGS = {1: {"001": 90, "011": 5, "100": 5},
            2: {"100": 650, "001": 60, "010": 40, "110": 100, "000": 100, "111": 50},
            3: {"100": 500, "001": 80, "010": 40, "101": 200, "000": 180},
            4: {"100": 620, "001": 90, "010": 50, "110": 90, "000": 150}}


class Counted(FakeSite):
    """A fake site that gives each order its own counts, with the same seconds."""

    def __init__(self, counts, seconds=1.5):
        super().__init__("euroqexa")
        self.counts, self.seconds = counts, seconds

    def result(self, job_id):
        self.calls.append(("result", job_id))
        return {"counts": self.counts.get(int(job_id.split("-")[1]), {"000": 1000}), "seconds": self.seconds}

    def submitted(self):
        return [c[1] for c in self.calls if c[0] == "submit"]


def own_copy(tmp_path):
    copy = tmp_path / "copy" / "state_transfer"
    shutil.copytree(FOLDER, copy)
    manifest = copy / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("MY-PROJECT", "EXAMPLE"), encoding="utf-8")
    return copy


def conf_for(budget=None):
    text = TOML.read_text(encoding="utf-8").replace("MY-PROJECT", "EXAMPLE")
    if budget is not None:
        text = text.replace("budget_seconds = 3000 ", f"budget_seconds = {budget} ", 1)
    return config.parse(text)


def overlap(made, wanted):
    """The size of the overlap of two states given by key: 1 for one state, up to a global phase."""
    return abs(sum(v.conjugate() * made.get(k, 0) for k, v in wanted.items()))


# ------------------------------------------------------------ the model and the hand text


def test_the_closed_form_arrives_in_full_at_t():
    assert closed_form(0.0)["001"] == pytest.approx(1.0)
    assert closed_form(T)["100"] == pytest.approx(1.0)
    assert closed_form(2 * T)["001"] == pytest.approx(1.0)
    assert closed_form(T / 2) == pytest.approx({"001": 0.25, "010": 0.5, "100": 0.25})
    assert abs(T - pi / sqrt(2)) < 1e-12


@pytest.mark.parametrize("t", [0.3, T / 4, T / 2, 3 * T / 4, T, 2 * T])
def test_the_amplitudes_square_to_the_closed_form(t):
    made = {key: abs(v) ** 2 for key, v in amplitudes(t).items()}
    assert made == pytest.approx(closed_form(t))


@pytest.mark.parametrize("t", [T / 4, T / 2, 3 * T / 4])
def test_the_hand_text_runs_time_forward_which_shares_alone_cannot_show(t):
    made = amplitudes_of(Steps(t, 128).text())
    assert overlap(made, amplitudes(t)) == pytest.approx(1.0, abs=1e-3)
    assert overlap(made, amplitudes(-t)) < 0.99          # the same shares, the other state
    assert closed_form(-t) == pytest.approx(closed_form(t))


def test_a_hand_step_is_a_bond_inside_the_quarter_turns():
    layers = Steps(T, 2).layers
    assert [bond for bond, _ in layers] == [BONDS[0], BONDS[1], BONDS[0], BONDS[1], BONDS[0]]
    assert [dt / (T / 2) for _, dt in layers] == pytest.approx([0.5, 1, 1, 1, 0.5])
    assert [bond for bond, _ in Steps(T, 2, 1).layers] == [BONDS[0], BONDS[1]] * 2
    text = Steps(T, 2).text()
    assert text.count("rx(1.5707963267948966)") == text.count("rx(-1.5707963267948966)") == SPINS
    assert control() == (FOLDER / "CONTROL.qasm").read_text(encoding="utf-8")


@pytest.mark.parametrize(("name", "case"), [("MAIN", Steps(T, 2)), ("HALF", Steps(T / 2, 2)),
                                            ("BACK", Steps(2 * T, 4)), ("ZERO", Steps(T, 2, excited=False)),
                                            ("STEPS1", Steps(T, 1)), ("STEPS4", Steps(T, 4)),
                                            ("STEPS8", Steps(T, 8)), ("ORDER1", Steps(T, 2, 1))])
def test_the_small_function_makes_the_hand_texts_again(name, case):
    assert case.text() == (FOLDER / f"{name}.qasm").read_text(encoding="utf-8")


# ------------------------------------------------------------ the files


def test_each_job_counts_its_gates_as_the_tutorial_says():
    assert [job["order"] for job in JOBS] == list(range(1, len(SIZES) + 1))
    for job in JOBS:
        text = (FOLDER / job["file"]).read_text(encoding="utf-8")
        parsed = Qasm.parse(text)
        assert parsed.qubits == SPINS
        assert (parsed.gate_count, job["two_qubit"]) == SIZES[job["name"]] and job["gates"] == parsed.gate_count
        assert parsed.gate_names <= {"x", "h", "rx", "rz", "cx", "cz", "measure"}


def test_repeat_is_the_same_text_as_main_and_control_takes_100_shots():
    assert (FOLDER / "MAIN.qasm").read_bytes() == (FOLDER / "REPEAT.qasm").read_bytes()
    shots = {job["name"]: job["shots"] for job in JOBS}
    assert shots.pop("CONTROL") == 100 and set(shots.values()) == {1000}


def test_the_chain_passes_the_euroqexa_dry_run_and_vlq_and_piastq_refuse_it(tmp_path):
    out = []
    assert dryrun.dry_run(MANIFEST, cfg=config.load(TOML), places=places_in(tmp_path), say=out.append) == 0, out
    for file in FOLDER.glob("*.qasm"):
        job = {"text": file.read_bytes(), "options": {}}
        assert any("not an OpenQASM 3 text" in p for p in SITES["vlq"].validate(job, None))
        assert any("not an operation list of the broker" in p for p in SITES["piastq"].validate(job, None))


# ------------------------------------------------------------ the numbers


@pytest.mark.parametrize("job", JOBS, ids=lambda j: j["name"])
def test_each_text_gives_what_its_line_of_the_manifest_says(job):
    made = shares_of((FOLDER / job["file"]).read_text(encoding="utf-8"))
    assert distance(made, job["text_shares"]) < 1e-5
    assert max(made, key=made.get) == job["key"]


@pytest.mark.parametrize("job", JOBS, ids=lambda j: j["name"])
def test_every_step_keeps_the_excitations_so_another_weight_is_a_machine_error(job):
    made = shares_of((FOLDER / job["file"]).read_text(encoding="utf-8"))
    assert sum(v for k, v in made.items() if k.count("1") == job["excitations"]) == pytest.approx(1.0, abs=1e-5)


@pytest.mark.parametrize("job", [j for j in JOBS if j["name"] in ARRIVALS], ids=lambda j: j["name"])
def test_the_share_of_the_arrival_is_as_the_tutorial_says(job):
    assert job["text_shares"]["100"] == pytest.approx(ARRIVALS[job["name"]], abs=5e-4)


def test_a_job_with_no_excitation_ends_in_all_zeros_at_any_steps():
    for case in (Steps(T, 1, excited=False), Steps(0.7, 3, excited=False), Steps(T, 8, 1, excited=False)):
        assert shares_of(case.text()) == {"000": 1.0}


# ------------------------------------------------------------ one send, and a send in two calls


def test_order_one_alone_then_the_rest_with_resume_and_no_order_twice(tmp_path, places, clock):
    copy, said = own_copy(tmp_path), []
    site, manifest = Counted(READINGS), copy / "manifest.json"
    code = runner.send(manifest, site, cfg=conf_for(10000), places=places, clock=clock, sleep=clock.sleep, host="h",
                       say=said.append, max_order=1)
    assert code == 0 and site.submitted() == [1]
    record = records_of(places)[0]
    assert [line for line in said if line.startswith("Go on with: ")] == [
        f"Go on with: qdevices send {manifest} --live --resume {record} --max-order N"]
    assert send(manifest, site, places, clock, conf_for(10000), host="h", resume=record, max_order=7) == 0
    assert site.submitted() == [1, 2, 3, 4, 5, 6, 7]
    assert send(manifest, site, places, clock, conf_for(10000), host="h", resume=record, max_order=7) == 0
    assert site.submitted() == [1, 2, 3, 4, 5, 6, 7] and records_of(places) == [record]


def test_a_second_send_is_refused_and_sends_nothing(tmp_path, places, clock):
    copy, site = own_copy(tmp_path), Counted(READINGS)
    manifest = copy / "manifest.json"
    assert send(manifest, site, places, clock, conf_for(10000), max_order=1) == 0
    clock.sleep(2)
    with pytest.raises(Refused, match="earlier record of this run"):
        send(manifest, site, places, clock, conf_for(10000), max_order=len(JOBS))
    assert site.submitted() == [1]


def test_a_small_budget_stops_early_and_resume_goes_on_and_the_example_budget_holds_all_jobs(tmp_path, places, clock):
    copy, site = own_copy(tmp_path), Counted(READINGS, seconds=144.0)
    manifest = copy / "manifest.json"
    assert send(manifest, site, places, clock, conf_for(1000), max_order=len(JOBS)) == 2
    assert site.submitted() == [1, 2, 3, 4]
    record = records_of(places)[0]
    assert send(manifest, site, places, clock, conf_for(), resume=record, max_order=len(JOBS)) == 0
    assert site.submitted() == list(range(1, len(JOBS) + 1))


def test_the_run_script_checks_once_then_sends_order_one_alone(tmp_path):
    copy, log = own_copy(tmp_path), tmp_path / "calls.log"
    stand_in = tmp_path / "bin" / "qdevices"
    stand_in.parent.mkdir()
    stand_in.write_text(f'#!/bin/sh\necho "$*" >> {log}\n', encoding="utf-8")
    stand_in.chmod(0o755)
    env = {"PATH": f"{stand_in.parent}{os.pathsep}/usr/bin:/bin", "MQSS_TOKEN": "x"}
    done = subprocess.run(["bash", str(copy / "run.sh"), "--live"], capture_output=True, text=True, check=False,
                          env=env)
    assert done.returncode == 0, done.stderr
    assert log.read_text(encoding="utf-8").splitlines() == ["check euroqexa --live --manifest manifest.json",
                                                            "send manifest.json --live --max-order 1"]


def test_the_run_script_refuses_the_placeholder_project():
    done = subprocess.run(["bash", str(FOLDER / "run.sh"), "--live"], capture_output=True, text=True, check=False,
                          env={"PATH": "/usr/bin:/bin"})
    assert done.returncode == 2 and "MY-PROJECT" in done.stderr


# ------------------------------------------------------------ the comparison


def test_the_counts_export_to_a_file_that_the_tutorial_reads_and_holds_no_id_or_time(tmp_path, places, clock):
    copy = own_copy(tmp_path)
    send(copy / "manifest.json", Counted(READINGS), places, clock, conf_for(10000), max_order=2)
    held = Compared.read(records_of(places)[0]).counts()
    assert set(held) == {"CONTROL", "MAIN"} and held["MAIN"] == READINGS[2]
    file = tmp_path / "live.json"
    file.write_text(json.dumps(held), encoding="utf-8")
    assert load_counts(str(file)) == held


def test_the_job_for_a_talk_is_the_text_and_the_line_of_hand():
    hand = next(job for job in JOBS if job["name"] == "MAIN")
    only = json.loads((LIVE / "manifest.json").read_text(encoding="utf-8"))["jobs"]
    assert only == [{**hand, "order": 1}]
    assert (LIVE / "MAIN.qasm").read_bytes() == (FOLDER / "MAIN.qasm").read_bytes()
    assert load_counts(str(LIVE / "results.json")) == {"MAIN": load_counts(str(FOLDER / "results.json"))["MAIN"]}


def test_compare_live_reads_the_newest_record_of_that_folder_and_writes_what_the_tutorial_reads(
        tmp_path, places, clock, monkeypatch, capsys):
    copy = tmp_path / "copy" / "live"
    shutil.copytree(LIVE, copy)
    manifest = copy / "manifest.json"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("MY-PROJECT", "EXAMPLE"), encoding="utf-8")
    written = tmp_path / "live.json"
    monkeypatch.setattr(Places, "default", classmethod(lambda cls: places))
    monkeypatch.setattr(compare, "LIVE", written)
    assert compare.main(["--live"]) == 1 and not written.exists()
    assert "No record of live/" in capsys.readouterr().out
    assert send(manifest, Counted({1: READINGS[2]}), places, clock, conf_for(10000), max_order=1) == 0
    assert compare.main(["--live"]) == 0
    assert load_counts(str(written)) == {"MAIN": READINGS[2]}
    assert "1 MAIN" in " ".join(capsys.readouterr().out.split())


def test_compare_takes_a_record_or_live_and_not_both(tmp_path):
    for argv in ([], [str(tmp_path / "r"), "--live"]):
        with pytest.raises(SystemExit):
            compare.main(argv)


def test_a_run_reads_its_folder_and_your_counts_take_the_place_of_the_same_jobs(tmp_path):
    first = Run.of(str(FOLDER))
    assert first.read["MAIN"].raw["100"] == pytest.approx(0.641) and first.read["MAIN"].shots == 1000
    assert len(first.table().splitlines()) == len(JOBS) + 1
    assert [row[:2] for row in first.over_steps()] == [(1, 6), (2, 10), (4, 18), (8, 34)]
    assert len(first.over_steps()[1][3]) == 2 and set(first.over_time()) == {0.0, T / 2, T, 2 * T}
    live = tmp_path / "live.json"
    live.write_text(json.dumps({"MAIN": READINGS[2]}), encoding="utf-8")
    second = Run.of(str(FOLDER), str(live))
    assert second.read["MAIN"].raw["100"] == pytest.approx(0.65)
    assert second.read["REPEAT"] == first.read["REPEAT"]


def test_the_numbers_of_hydrogen_read_as_the_tutorial_says():
    assert [round(size.energy, 3) for size in MADE.sizes] == [-1.571, -1.963, -1.767, -1.865]
    assert [size.gates for size in MADE.sizes] == [261, 558, 1142, 2307]
    assert max(MADE.energies, key=MADE.energies.get) == -1.865
    assert "The exact energy: -1.857 hartree" in MADE.table() and len(MADE.table().splitlines()) == 6


def test_the_results_of_the_run_are_in_the_folder():
    held = load_counts(str(FOLDER / "results.json"))
    assert set(held) == {job["name"] for job in JOBS}
    assert Reading(held["MAIN"]).raw["100"] == pytest.approx(0.641)
    assert Reading(held["STEPS8"]).raw["100"] == pytest.approx(0.19)


def test_the_tutorial_says_what_ran_as_the_job_pages_of_the_portal_show():
    book = json.loads((HERE / "tutorial.ipynb").read_text(encoding="utf-8"))
    cells = {cell.get("id"): "".join(cell["source"]) for cell in book["cells"]}
    two = {job["name"]: job["two_qubit"] for job in JOBS}
    said = " ".join(cells[name] for name in ("cell-18", "cell-20", "cell-24", "curve-after"))
    assert not [w for w in ("very likely", "inferred", "have not read", "do not show how many") if w in said]
    assert "what follows about the compile is read on the job pages of the portal" in cells["cell-18"]
    assert f"so gates did run, and the circuit that ran has all {two['ZERO']} CZ" in cells["cell-20"]
    assert f"For QRISP it has {two['MAIN']} CZ, as for MAIN" in cells["cell-20"] and two["QRISP"] == 2 * two["MAIN"]
    assert f"its executed circuit has all {two['BACK']} CZ: it was not cut to three bonds" in cells["cell-20"]
    assert f"every two-qubit gate of its text ({two['STEPS8']} CZ for STEPS8)" in cells["cell-24"]
    assert "the compile merged the gates of one pair of qubits (Executed Circuit on the portal)" in cells["curve-after"]
    binder = "https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=lab/tree/examples/all_examples.ipynb"
    assert f"blob/main/examples/all_examples.ipynb), also [on Binder]({binder})." in cells["cell-30"]


def test_a_reading_counts_raw_and_post_selected_shares():
    read = Reading(READINGS[2])
    assert read.raw["100"] == pytest.approx(0.65) and read.kept == pytest.approx(0.75)
    assert read.post["100"] == pytest.approx(0.65 / 0.75)
    assert set(read.post) == {"100", "001", "010"}


def test_a_reading_of_a_job_with_no_excitation_keeps_all_zeros():
    read = Reading({"000": 700, "001": 300}, excitations=0)
    assert read.kept == pytest.approx(0.7) and read.post == {"000": 1.0}


def test_compare_reads_a_record_in_the_key_order_of_the_site(tmp_path, places, clock):
    copy = own_copy(tmp_path)
    send(copy / "manifest.json", Counted(READINGS), places, clock, conf_for(10000), max_order=4)
    table = Compared.read(records_of(places)[0]).table()
    assert len(table) == len(JOBS) + 1 and table[1].split()[:5] == ["1", "CONTROL", "0", "100", "001"]
    cells = {line.split()[1]: line.split() for line in table[1:]}
    assert [float(x) for x in cells["CONTROL"][5:10]] == pytest.approx([1.0, 1.0, 0.9, 0.95, 0.947], abs=1e-3)
    assert [float(x) for x in cells["MAIN"][5:10]] == pytest.approx([1.0, 0.970, 0.65, 0.75, 0.867], abs=1e-3)
    assert cells["MAIN"][4] == "100" and cells["HALF"][4] == "010" and cells["ZERO"][4] == "000"


def test_a_reversed_reading_shows_as_no_transfer(tmp_path, places, clock):
    copy = own_copy(tmp_path)
    reversed_keys = {order: {key[::-1]: n for key, n in counts.items()} for order, counts in READINGS.items()}
    send(copy / "manifest.json", Counted(reversed_keys), places, clock, conf_for(10000), max_order=2)
    table = Compared.read(records_of(places)[0]).table()
    assert float(table[2].split()[7]) == pytest.approx(0.06) and float(table[1].split()[7]) == pytest.approx(0.05)


def test_compare_shows_what_was_not_sent_and_stops_on_a_key_of_another_width(tmp_path, places, clock):
    copy = own_copy(tmp_path)
    site = Counted({1: READINGS[1], 2: {"0100": 1000}})
    send(copy / "manifest.json", site, places, clock, conf_for(10000), max_order=2)
    table = Compared.read(records_of(places)[0]).table()
    assert table[2].endswith("a key of another width: read the record")
    assert table[3].endswith("not sent")


# ------------------------------------------------------------ with Qrisp


@pytest.fixture(scope="module")
def chain_written(tmp_path_factory):
    """The two folders as write_chain.py writes them now, in a process of its own."""
    pytest.importorskip("qrisp")
    out = tmp_path_factory.mktemp("chain")
    subprocess.run([sys.executable, HERE / "write_chain.py", "--out", out], check=True, capture_output=True)
    return out


def test_qrisp_makes_the_same_files_again_and_the_same_answer_as_the_hand_text(chain_written):
    for folder in (FOLDER, LIVE):
        for file in (f for f in folder.iterdir() if f.name not in KEPT):
            assert (chain_written / folder.name / file.name).read_bytes() == file.read_bytes(), file.name
    assert distance(shares_of((FOLDER / "QRISP.qasm").read_text(encoding="utf-8")),
                    shares_of((FOLDER / "MAIN.qasm").read_text(encoding="utf-8"))) < 1e-5


def test_made_with_names_qrisp_only_where_a_text_comes_from_it_and_no_other_key_changes(chain_written):
    """state_transfer holds QRISP, by Qrisp, and ten texts by chain.py; live holds the MAIN of chain.py alone."""
    said = {"state_transfer": "Qrisp and a small function, examples/hamiltonian/write_chain.py",
            "live": "a small function, examples/hamiltonian/write_chain.py"}
    for folder in (FOLDER, LIVE):
        made = json.loads((chain_written / folder.name / "manifest.json").read_text(encoding="utf-8"))
        kept = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        assert made["made_with"] == said[folder.name]
        assert {**made, "made_with": ""} == {**kept, "made_with": ""}
        for job in made["jobs"]:
            assert (chain_written / folder.name / job["file"]).read_bytes() == (folder / job["file"]).read_bytes()


def test_made_with_puts_qrisp_first_and_names_each_maker_once():
    pytest.importorskip("qrisp")
    from write_chain import SMALL, Job, made_with

    def job(name, made=SMALL):
        return Job(name, "", "T", T, 2, made=made)

    assert made_with((job("MAIN"), job("REPEAT"))) == f"{SMALL}, examples/hamiltonian/write_chain.py"
    assert made_with((job("MAIN"), job("QRISP", "Qrisp"))) == f"Qrisp and {SMALL}, examples/hamiltonian/write_chain.py"
    assert made_with((job("QRISP", "Qrisp"),)) == "Qrisp, examples/hamiltonian/write_chain.py"
    assert made_with((job("MAIN", "Python"), job("QRISP", "Qrisp"))) == (      # Python sorts before Qrisp
        "Qrisp and Python, examples/hamiltonian/write_chain.py")


def test_qrisp_makes_the_numbers_of_hydrogen_again():
    pytest.importorskip("qrisp")
    from with_qrisp import hydrogen
    made = hydrogen()
    assert made.exact == pytest.approx(MADE.exact, abs=5e-4)
    assert [(s.bits, s.qubits, s.gates) for s in made.sizes] == [(s.bits, s.qubits, s.gates) for s in MADE.sizes]
    assert [s.phase for s in made.sizes] == pytest.approx([s.phase for s in MADE.sizes])
    assert sum(made.energies.values()) == pytest.approx(1.0, abs=1e-6)
    for energy, share in MADE.energies.items():
        nearest = min(made.energies, key=lambda e: abs(e - energy))
        assert made.energies[nearest] == pytest.approx(share, abs=1e-4)


def test_the_matrices_hold_what_the_tutorial_says_of_them():
    np = pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    from matrices import Formula, H, JordanWigner, bond, exact, pauli
    from scipy.linalg import expm
    assert np.allclose(bond(0.7), expm(-0.35j * (pauli("XX") + pauli("YY"))))
    assert Formula(T, 32, 2).error() / Formula(T, 64, 2).error() == pytest.approx(4, abs=0.1)
    assert Formula(T, 32, 1).error() / Formula(T, 64, 1).error() == pytest.approx(2, abs=0.1)
    assert np.allclose(exact(2 * T), np.eye(8))
    three = JordanWigner(3)
    assert np.allclose(three.hop(0, 1) + three.hop(1, 2), H)
    assert np.allclose(three.hop(0, 2), 0.5 * (pauli("XZX") + pauli("YZY")))


def test_the_tables_hold_a_line_for_each_case():
    pytest.importorskip("scipy")
    from tables import arrival, formulas, rise_and_fall, routes
    assert len(routes().splitlines()) == 5 and len(formulas().splitlines()) == 6
    assert len(rise_and_fall(steps=(1, 2)).splitlines()) == 3
    assert arrival(2, 0.0, 0.0) == pytest.approx(0.970, abs=0.02)


def test_the_hop_of_an_electron_is_the_bond_of_the_chain():
    pytest.importorskip("qrisp")
    np = pytest.importorskip("numpy")
    from qrisp.operators import X, Y, a, c
    bond = (0.5 * (X(0) * X(1) + Y(0) * Y(1))).to_array()
    hop = (c(0) * a(1) + c(1) * a(0)).to_qubit_operator().to_array()
    assert np.allclose(hop, bond)
