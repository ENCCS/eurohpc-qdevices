"""Each example folder explains itself: its README, its scripts, what they do, and the emulator behind them."""

import json
import os
import shutil
import subprocess
import sys
from math import pi
from pathlib import Path

import pytest
from fakes import FakeSite, records_of, send
from test_scan import banned, dates, heads, text_of

from qdevices import config
from qdevices.paths import Places
from qdevices.record import RecordLines

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
import counts  # noqa: E402
import dry_run  # noqa: E402
import folders  # noqa: E402
from circuit import Circuit, circuit_of  # noqa: E402
from emulate import Report  # noqa: E402
from emulate import main as emulate_main  # noqa: E402
from example_folder import SCRIPT_MODELS, ExampleFolder  # noqa: E402
from overview import Overview  # noqa: E402
from texts import angle  # noqa: E402

FOLDERS = sorted(p.parent for p in EXAMPLES.rglob("manifest.json") if ".pixi" not in p.parts)
NAMES = [f.relative_to(EXAMPLES).as_posix() for f in FOLDERS]
TOKENS = {"euroqexa": "MQSS_TOKEN", "vlq": "LEXIS_TOKEN", "piastq": "PCSS_API_KEY"}
PERFECT = {"euroqexa-one-qubit": {"1"}, "euroqexa-bell": {"00", "11"}, "euroqexa-ghz": {"000", "111"},
           "euroqexa-inverse": {"011"}, "vlq-one-qubit": {"1"}, "vlq-bell": {"00", "11"},
           "vlq-ghz": {"00000", "11111"}, "piastq-one-qubit": {"1"}, "piastq-bell": {"00", "11"},
           "piastq-native": {"00", "01", "10", "11"}, "qrisp/bv4": {"01101"}, "qrisp/add_const": {"110"},
           "qrisp/grover3": {"110"}, "qrisp/qft3": {"101"}, "hamiltonian/live": {"100", "001"}}
NOTEBOOKS = (EXAMPLES / "all_examples.ipynb", EXAMPLES / "hamiltonian" / "tutorial.ipynb")


def run_script(folder, *args, stand_in=(), home=None, tokens=(), script="run.sh"):
    """A script of a folder, with a stand-in for each command named, which logs its arguments."""
    bin_dir = home.parent / "bin" if home else folder.parent / "bin"
    bin_dir.mkdir(exist_ok=True)
    log = bin_dir / "calls.log"
    for command in stand_in:
        path = bin_dir / command
        path.write_text(f'#!/bin/sh\necho "{command} $*" >> {log}\n', encoding="utf-8")
        path.chmod(0o755)
    env = {"PATH": f"{bin_dir}{os.pathsep}/usr/bin:/bin", **({"HOME": str(home)} if home else {}),
           **dict.fromkeys(tokens, "x")}
    done = subprocess.run(["bash", str(folder / script), *args], capture_output=True, text=True, check=False, env=env)
    return done, log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def copy_of(name, tmp_path, *, real_names=True):
    """A folder in a stand-in clone: a pyproject of the app two levels up, the manifest with your names if asked."""
    root = tmp_path / "clone"
    (root / "examples").mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\nname = "eurohpc-qdevices"\n', encoding="utf-8")
    folder = root / "examples" / name
    shutil.copytree(EXAMPLES / name, folder)
    if real_names:
        manifest = folder / "manifest.json"
        manifest.write_text(manifest.read_text(encoding="utf-8").replace("MY-", "OUR-"), encoding="utf-8")
    return folder


def with_config(tmp_path):
    home = tmp_path / "home"
    (home / ".config" / "qdevices").mkdir(parents=True)
    (home / ".config" / "qdevices" / "qdevices.toml").write_text("", encoding="utf-8")
    return home


# ------------------------------------------------------------ the folders


@pytest.mark.parametrize("folder", FOLDERS, ids=NAMES)
def test_each_folder_has_the_same_three_scripts_and_they_are_executable(folder):
    for model, script in SCRIPT_MODELS.items():
        assert (folder / script).read_bytes() == (EXAMPLES / "tools" / model).read_bytes(), script
        assert os.access(folder / script, os.X_OK), script


@pytest.mark.parametrize("folder", FOLDERS, ids=NAMES)
def test_each_folder_has_a_readme_that_says_how_to_run_it_and_names_its_files(folder):
    text = (folder / "README.md").read_text(encoding="utf-8")
    site = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["site"]
    for words in ("## Emulate it", "./emulate.sh", "./run.sh", "./submit.sh", "./run.sh --counts", "mybinder.org",
                  "examples/qdevices.toml", TOKENS[site], "```mermaid", "**What a perfect machine gives:**",
                  "**What came back:**", "## The files", "`manifest.json`", "git clone"):
        assert words in text, words
    for job in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"]:
        assert f"`{job['file']}`" in text or "`*.qasm`" in text, job["file"]


def test_the_hand_written_folders_hold_what_folders_py_writes():
    assert set(folders.READMES) == {f.name for f in FOLDERS if f.parent == EXAMPLES}
    for name, page in folders.READMES.items():
        assert (EXAMPLES / name / "README.md").read_text(encoding="utf-8") == page.text(name), name


def test_a_folder_on_disk_gets_the_page_and_the_scripts_of_its_readme(tmp_path):
    name = "euroqexa-bell"
    ExampleFolder(tmp_path / name, name).write_page(folders.READMES[name])
    for file in ("README.md", *SCRIPT_MODELS.values()):
        assert (tmp_path / name / file).read_bytes() == (EXAMPLES / name / file).read_bytes(), file
    assert os.access(tmp_path / name / "emulate.sh", os.X_OK)


def test_the_overview_holds_each_job_and_leaves_the_read_empty_for_one_not_sent():
    overview = Overview.of(EXAMPLES)
    assert len(overview.folders) == len(FOLDERS)
    rows = {(Path(row.folder).name, row.job): row for row in overview.rows}
    assert rows["grover3", "GROVER3"].read == pytest.approx(0.351) and rows["grover3", "GROVER3"].gates == 24
    assert rows["euroqexa-ghz", "GHZ"].read is None
    assert len(overview.table().splitlines()) == len(rows) + 1


def test_the_readmes_above_the_folders_name_each_of_them():
    top = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    for name in {*folders.READMES, "hamiltonian", "qrisp"}:
        assert f"{name}/README.md" in top, name
    qrisp = (EXAMPLES / "qrisp" / "README.md").read_text(encoding="utf-8")
    for folder in (f for f in FOLDERS if f.parent == EXAMPLES / "qrisp"):
        assert f"{folder.name}/README.md" in qrisp, folder.name


# ------------------------------------------------------------ the scripts


def test_a_dry_run_goes_through_the_clone_and_writes_nothing_in_the_home_folder(tmp_path):
    folder, home = copy_of("euroqexa-bell", tmp_path, real_names=False), tmp_path / "home"
    home.mkdir()
    done, calls = run_script(folder, stand_in=["pixi"], home=home)
    assert done.returncode == 0, done.stderr
    root = folder.parent.parent
    assert calls == [f"pixi run --frozen --manifest-path {root}/pyproject.toml python {root}/examples/tools/dry_run.py "
                     "manifest.json"]
    assert "README.md" in done.stdout


@pytest.mark.parametrize("name", ["euroqexa-bell", "vlq-one-qubit", "piastq-one-qubit"])
def test_submit_reads_once_then_sends_the_first_job_with_the_token_of_its_site(tmp_path, name):
    folder, home = copy_of(name, tmp_path), with_config(tmp_path)
    site = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["site"]
    done, calls = run_script(folder, stand_in=["qdevices"], home=home, tokens=[TOKENS[site]], script="submit.sh")
    assert done.returncode == 0, done.stderr
    assert calls == [f"qdevices check {site} --live --manifest manifest.json",
                     "qdevices send manifest.json --live --max-order 1"]


def test_submit_refuses_any_option_and_sends_nothing(tmp_path):
    folder, home = copy_of("euroqexa-bell", tmp_path), with_config(tmp_path)
    for option in ("--help", "--dry-run", "x"):
        done, calls = run_script(folder, option, stand_in=["qdevices"], home=home, tokens=["MQSS_TOKEN"],
                                 script="submit.sh")
        assert done.returncode == 2 and "Nothing was sent" in done.stderr and calls == []


def test_a_live_run_stops_with_no_token_and_says_how_to_get_one(tmp_path):
    home = with_config(tmp_path)
    done, calls = run_script(copy_of("vlq-one-qubit", tmp_path), "--live", stand_in=["qdevices"], home=home)
    assert done.returncode == 2 and "LEXIS_TOKEN is not set: nothing was sent" in done.stderr and calls == []


def test_a_live_run_stops_with_no_config_and_names_the_example(tmp_path):
    folder, home = copy_of("euroqexa-bell", tmp_path), tmp_path / "home"
    home.mkdir()
    done, calls = run_script(folder, "--live", stand_in=["qdevices"], home=home, tokens=["MQSS_TOKEN"])
    assert done.returncode == 2 and "cp examples/qdevices.toml" in done.stderr and calls == []


def test_a_live_run_refuses_a_placeholder_before_any_call(tmp_path):
    done, calls = run_script(copy_of("vlq-one-qubit", tmp_path, real_names=False), "--live", stand_in=["qdevices"],
                             tokens=["LEXIS_TOKEN"])
    assert done.returncode == 2 and "MY-PROJECT" in done.stderr and calls == []


def test_login_asks_the_app_for_the_site_of_the_manifest(tmp_path):
    done, calls = run_script(copy_of("piastq-bell", tmp_path), "--login", stand_in=["qdevices"])
    assert done.returncode == 0 and calls == ["qdevices login piastq"]


def test_emulate_needs_python_and_a_clone_and_nothing_else(tmp_path):
    outside = tmp_path / "alone"
    shutil.copytree(EXAMPLES / "euroqexa-bell", outside)
    done, _ = run_script(outside, script="emulate.sh", home=tmp_path / "h")
    assert done.returncode == 2 and "clone of the repository" in done.stderr
    env = {"PATH": f"{Path(sys.executable).parent}{os.pathsep}/usr/bin:/bin"}
    done = subprocess.run(["bash", str(EXAMPLES / "euroqexa-bell" / "emulate.sh")], capture_output=True, text=True,
                          check=False, env=env)
    assert done.returncode == 0, done.stderr
    assert "a perfect machine" in done.stdout and "nothing was sent" in done.stdout


# ------------------------------------------------------------ the emulator


@pytest.mark.parametrize("name", sorted(PERFECT), ids=str)
def test_the_emulator_gives_the_answers_the_readmes_name(name):
    folder = EXAMPLES / name
    job = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"][0]
    shares = circuit_of(folder / job["file"]).shares()
    assert sum(shares.values()) == pytest.approx(1.0)
    assert {key for key, value in shares.items() if value > 0.01} == PERFECT[name]


@pytest.mark.parametrize("name", sorted(PERFECT), ids=str)
def test_each_answer_is_named_in_the_readme_of_its_folder(name):
    text = (EXAMPLES / name / "README.md").read_text(encoding="utf-8")
    assert all(key in text for key in PERFECT[name]), name


@pytest.mark.parametrize("line", ["x q;", "measure q -> c;", "ccx q[0],q[1],q[2];", "reset q[0];"])
def test_the_emulator_names_a_line_it_does_not_take(line):
    with pytest.raises(ValueError, match="does not take"):
        Circuit.of_text(f"qreg q[3];\ncreg c[3];\n{line}\nmeasure q[0] -> c[0];\n")


def test_the_emulator_refuses_two_registers_and_passes_over_comments():
    with pytest.raises(ValueError, match="one quantum register"):
        Circuit.of_text("qreg a[1];\nqreg b[1];\nx a[0];\n")
    assert Circuit.of_text("// a note\nqreg q[1];\ncreg c[1];\nx q[0]; // flip\nmeasure q[0] -> c[0];\n").shares() == {
        "1": pytest.approx(1.0)}


def test_the_emulator_takes_every_gate_the_writer_of_the_examples_writes():
    text = ("qreg q[2];\ncreg c[2];\ny q[0];\nz q[0];\ns q[1];\nsdg q[1];\nry(0.3) q[0];\nu3(0.1,0.2,0.3) q[1];\n"
            "cy q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n")
    assert sum(Circuit.of_text(text).shares().values()) == pytest.approx(1.0)


def test_the_broker_list_names_an_operation_it_does_not_know():
    with pytest.raises(ValueError, match="not an operation"):
        Circuit.of_list({"number_of_qubits": 1, "quantum_circuit": [{"operation": "Rxx"}]})


def test_the_noise_option_refuses_a_chance_outside_zero_to_one(capsys):
    with pytest.raises(SystemExit):
        emulate_main([str(EXAMPLES / "qrisp" / "bell" / "manifest.json"), "--noise", "3"])
    assert "chances from 0 to 1" in capsys.readouterr().err


def test_the_emulator_holds_a_wide_register_as_only_what_is_not_zero():
    shares = circuit_of(EXAMPLES / "qrisp" / "hello" / "HELLO.qasm").shares()
    assert shares == {"0111001011010110010000111": pytest.approx(1.0)}


def test_the_emulator_reads_angles_with_pi_and_nothing_else():
    assert angle("-pi/2") == pytest.approx(-pi / 2) and angle("2*pi - 1") == pytest.approx(2 * pi - 1)
    with pytest.raises(ValueError, match="not an angle"):
        angle("__import__('os')")


def test_the_broker_list_reads_qubit_zero_first():
    made = Circuit.of_list({"number_of_qubits": 2, "quantum_circuit": [{"operation": "R", "qubit": 0, "theta": 1.0,
                                                                       "phi": 0.0}, {"operation": "MEASURE"}]})
    assert made.shares() == {"10": pytest.approx(1.0)}


def test_a_text_reads_the_highest_classical_bit_first():
    text = "qreg q[2];\ncreg c[2];\nx q[0];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n"
    assert Circuit.of_text(text).shares() == {"01": pytest.approx(1.0)}


def test_noise_spreads_the_counts_and_keeps_their_sum_and_is_the_same_again():
    circuit = circuit_of(EXAMPLES / "qrisp" / "bell" / "BELL.qasm")
    assert set(circuit.sample(1000)) == {"00", "11"} and sum(circuit.sample(1000).values()) == 1000
    noisy = circuit.sample(1000, noise=0.3, readout=0.05)
    assert sum(noisy.values()) == 1000 and {"01", "10"} <= set(noisy)
    assert noisy == circuit.sample(1000, noise=0.3, readout=0.05)


def test_the_report_shows_what_came_back_where_it_ran():
    lines = Report(EXAMPLES / "qrisp" / "grover3" / "manifest.json", shots=100, noise=0.01, readout=0.01).lines()
    assert lines[0].startswith("GROVER3") and "a perfect machine  110: 1.000" in lines[1]
    assert "emulated, with noise" in lines[4] and "the machine, once  110: 0.351" in lines[5]


@pytest.mark.parametrize("results", sorted(EXAMPLES.rglob("results.json")), ids=lambda p: p.parent.name)
def test_each_results_file_holds_counts_of_the_jobs_of_its_folder(results):
    held = json.loads(results.read_text(encoding="utf-8"))
    manifest = json.loads((results.parent / "manifest.json").read_text(encoding="utf-8"))
    jobs = {job["name"]: job for job in manifest["jobs"]}
    assert held and set(held) <= set(jobs)
    width = len(circuit_of(results.parent / jobs[next(iter(held))]["file"]).bits)
    for name, counts_of_job in held.items():
        assert all(type(n) is int and n > 0 for n in counts_of_job.values()), name
        assert all(len(key) == width and set(key) <= {"0", "1"} for key in counts_of_job), name
        if results.parent.name != "piastq-bell":          # it ran at 200 shots, and the example takes 100
            assert sum(counts_of_job.values()) == jobs[name]["shots"], name


# ------------------------------------------------------------ the two small scripts of a send


def test_a_dry_run_uses_the_example_config_for_a_placeholder_and_yours_for_your_names(tmp_path):
    own = tmp_path / "qdevices.toml"
    own.write_text("", encoding="utf-8")
    placeholder, mine = tmp_path / "a.json", tmp_path / "b.json"
    placeholder.write_text('{"project": "MY-PROJECT"}', encoding="utf-8")
    mine.write_text('{"project": "OURS"}', encoding="utf-8")
    assert dry_run.config_for(placeholder, own) == dry_run.EXAMPLE
    assert dry_run.config_for(mine, own) == own
    assert dry_run.config_for(mine, tmp_path / "none.toml") == dry_run.EXAMPLE


def test_an_example_passes_its_dry_run_with_a_config_that_lists_only_your_own_project(tmp_path, monkeypatch, capsys):
    own = tmp_path / "qdevices.toml"
    own.write_text('[euroqexa]\nprojects = ["OURS"]\nbudget_seconds = 1\n', encoding="utf-8")
    places = Places(records=tmp_path / "r", reads=tmp_path / "s", state=tmp_path / "t", config=own)
    monkeypatch.setattr(Places, "default", classmethod(lambda cls: places))
    assert dry_run.main([str(EXAMPLES / "euroqexa-bell" / "manifest.json")]) == 0
    assert "This dry run uses examples/qdevices.toml." in capsys.readouterr().out
    assert not any(place.exists() for place in (places.records, places.reads, places.state))


def test_counts_shows_the_top_keys_and_the_state_of_each_order(tmp_path, places, clock):
    manifest = EXAMPLES / "euroqexa-three-jobs" / "manifest.json"
    copy = tmp_path / "three"
    shutil.copytree(manifest.parent, copy)
    (copy / "manifest.json").write_text(manifest.read_text(encoding="utf-8").replace("MY-PROJECT", "EXAMPLE"),
                                        encoding="utf-8")
    conf = config.parse((EXAMPLES / "qdevices.toml").read_text(encoding="utf-8").replace("MY-PROJECT", "EXAMPLE"))
    send(copy / "manifest.json", FakeSite("euroqexa"), places, clock, conf, max_order=1)
    rows = counts.lines(RecordLines.read(records_of(places)[0]).events)
    assert rows[0].startswith("X") and "shots" in rows[0] and rows[1].split()[0] == "BELL" and "shots" not in rows[1]


# ------------------------------------------------------------ the notebooks


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_a_notebook_holds_its_outputs_and_no_error_and_stays_out_of_the_docs_execution(path):
    book = json.loads(path.read_text(encoding="utf-8"))
    code = [c for c in book["cells"] if c["cell_type"] == "code"]
    assert code and all(c["outputs"] for c in code[1:])
    assert not [o for c in code for o in c["outputs"] if o["output_type"] == "error"]
    assert book["metadata"]["mystnb"] == {"execution_mode": "off"}


@pytest.mark.parametrize("path", NOTEBOOKS, ids=lambda p: p.name)
def test_a_notebook_is_public_text_and_needs_no_app_and_no_token(path):
    book = json.loads(path.read_text(encoding="utf-8"))
    sources = "".join("".join(c["source"]) for c in book["cells"])
    text = text_of(path)
    assert not dates(text), dates(text)
    assert not [c for c in book["cells"] if "execution" in c["metadata"]]
    assert not banned(text.lower(), heads([text.lower()]))
    for word in ("getpass", "import qdevices", "from qdevices", "advantage", "safety"):
        assert word not in sources, word
    assert chr(0x2014) not in sources and chr(0x2013) not in sources


def test_the_page_of_all_the_examples_holds_each_folder():
    book = json.loads(NOTEBOOKS[0].read_text(encoding="utf-8"))
    code = (c for c in book["cells"] if c["cell_type"] == "code")
    printed = "".join("".join(o.get("text", "")) for c in code for o in c["outputs"])
    assert f"{len(FOLDERS)} examples" in printed
    assert all(name in printed for name in NAMES)


def test_binder_gets_the_notebooks_what_they_need_and_not_the_app():
    needs = (EXAMPLES.parent / ".binder" / "requirements.txt").read_text(encoding="utf-8").split()
    assert {"scipy", "matplotlib", "qutip==5.3.1", "qutip-qip==0.4.2", "qrisp==0.9.10"} <= set(needs)
    assert "." not in needs
    assert (EXAMPLES.parent / ".binder" / "runtime.txt").read_text(encoding="utf-8").strip() == "python-3.12"
