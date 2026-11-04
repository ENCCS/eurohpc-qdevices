"""The --qasm of each Euro-Q-Exa script: the OpenQASM 2 text that QuTiP and Qrisp code give, read back and compared.

The texts are read by the parser of the examples and must give the shares of the text that was sent. Qrisp's, through
examples/qrisp/qasm2.py, gives the same bytes as the text sent, but for INVERSE: there crz is built from rz and cx,
the register meas is written c, and the barrier is left out. The last test watches these paths for a call to a module
on the scan list of test_scan.py.
"""

import hashlib
import re
import runpy
import sys
from pathlib import Path

import pytest
from fakes import QELIB1
from test_qrisp_emulator_path import CalledModules
from test_scan import BANNED

from qdevices.qasm import Qasm

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from circuit import Circuit, circuit_of  # noqa: E402
from emulate import jobs_of, qrisp_stored, qutip_stored, top  # noqa: E402
from overview import example_folders, largest_apart  # noqa: E402
from script_qasm import for_qasm  # noqa: E402

FOLDERS = [folder for folder in example_folders(EXAMPLES) if for_qasm(folder)]
JOBS = [(folder, job) for folder in FOLDERS for job in jobs_of(folder)]
IDS = [f"{folder.relative_to(EXAMPLES).as_posix()}-{job['name']}" for folder, job in JOBS]
SCRIPTS = {"emulate_qutip.py": "qutip_qip", "emulate_qrisp.py": "qrisp"}       # each script and what it needs
ALLOWED = QELIB1 | {"U", "CX", "measure"}                                    # U and CX are built into OpenQASM 2
# Qrisp has no crz method, so INVERSE's crz is built from rz and cx; its register meas is written c, and its barrier,
# which the parser of the examples skips, is left out.
BUILT = {("euroqexa-inverse", "INVERSE")}


def is_qasm2(text: str) -> bool:
    """One OpenQASM 2 header, and a semicolon after each measure."""
    lines = text.splitlines()
    return lines.count("OPENQASM 2.0;") == 1 and all(line.endswith(";") for line in lines if line.startswith("measure"))


def text_of(names: dict, job: str) -> str:
    """What to_qasm of a script gives for one job: a QuTiP job is (build, read), a Qrisp job is build alone."""
    built = names["JOBS"][job]
    return names["to_qasm"](built[0](), built[1]) if isinstance(built, tuple) else names["to_qasm"](built())


def run_main(script: Path, argv: list, monkeypatch) -> dict:
    """A script run as a program, with these arguments after its name; the names it holds at the end."""
    pytest.importorskip(SCRIPTS[script.name])
    monkeypatch.setattr(sys, "argv", [script.name, *argv])
    return runpy.run_path(str(script), run_name="__main__")


def test_only_the_euroqexa_folders_have_a_qasm_part():
    assert len(FOLDERS) == 24
    for folder in example_folders(EXAMPLES):
        assert ("def to_qasm" in (folder / "emulate_qutip.py").read_text(encoding="utf-8")) == (folder in FOLDERS)
        assert ("def to_qasm" in (folder / "emulate_qrisp.py").read_text(encoding="utf-8")) == (folder in FOLDERS)


@pytest.mark.parametrize("folder", FOLDERS, ids=[folder.relative_to(EXAMPLES).as_posix() for folder in FOLDERS])
def test_each_readme_keeps_the_text_of_a_job_of_its_manifest_in_a_file(folder):
    page, path = (folder / "README.md").read_text(encoding="utf-8"), folder.relative_to(EXAMPLES).as_posix()
    named = re.findall(r"`python emulate_qutip\.py --qasm (\S+) > mine\.qasm`", page)
    assert len(named) == 1 and named[0] in {job["name"] for job in jobs_of(folder)}, named
    assert f"puts the text of the job {named[0]} in `mine.qasm`" in page
    assert f"python examples/{path}/emulate_qutip.py --qasm {named[0]} > examples/{path}/mine.qasm`" in page
    several = len(jobs_of(folder)) > 1
    assert ("with no job name, `--qasm` prints the text of each job" in page) == several
    assert ("a file to send holds one job" in page) == several == ("each other job that names the same file" in page)


@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_qutips_text_reads_back_to_the_shares_of_the_text_sent_with_gates_of_qelib1(folder, job):
    pytest.importorskip("qutip_qip")
    script = runpy.run_path(str(folder / "emulate_qutip.py"))
    build, read = script["JOBS"][job["name"]]
    text = script["to_qasm"](build(), read)
    names = Qasm.parse(text).gate_names
    assert names <= ALLOWED and is_qasm2(text), names - ALLOWED
    assert largest_apart(Circuit.of_text(text).shares(), circuit_of(folder / job["file"]).shares()) < 1e-9


@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_qrisps_text_is_the_text_sent_but_for_inverse(folder, job):
    pytest.importorskip("qrisp")
    script = runpy.run_path(str(folder / "emulate_qrisp.py"))
    text, sent = script["to_qasm"](script["JOBS"][job["name"]]()), (folder / job["file"]).read_text(encoding="utf-8")
    assert (text == sent) != ((folder.relative_to(EXAMPLES).as_posix(), job["name"]) in BUILT)
    names = Qasm.parse(text).gate_names
    assert names <= ALLOWED and is_qasm2(text), names - ALLOWED
    assert largest_apart(Circuit.of_text(text).shares(), circuit_of(folder / job["file"]).shares()) < 1e-9


def test_qutips_to_qasm_refuses_a_measurement_and_a_classical_control():
    circuit = pytest.importorskip("qutip_qip.circuit")
    to_qasm = runpy.run_path(str(EXAMPLES / "euroqexa-bell" / "emulate_qutip.py"))["to_qasm"]
    measured, controlled = circuit.QubitCircuit(2, num_cbits=1), circuit.QubitCircuit(2, num_cbits=1)
    measured.add_measurement("M", targets=[0], classical_store=0)
    controlled.add_gate("X", targets=[1], classical_controls=[0])
    for qc in (measured, controlled):
        with pytest.raises(ValueError, match="gates only"):
            to_qasm(qc, [1, 0])


def test_qutips_to_qasm_puts_a_point_before_an_exponent():
    """qutip-qip writes 1e-05; OpenQASM 2 needs a point in a real, as examples/qrisp/qasm2.py writes it."""
    circuit = pytest.importorskip("qutip_qip.circuit")
    to_qasm = runpy.run_path(str(EXAMPLES / "euroqexa-bell" / "emulate_qutip.py"))["to_qasm"]
    qc = circuit.QubitCircuit(1)
    for value in (1e-05, 1.5e-07, -2e-16):
        qc.add_gate("RZ", targets=[0], arg_value=value)
    assert "rz(1.0e-05) q[0];\nrz(1.5e-07) q[0];\nrz(-2.0e-16) q[0];\n" in to_qasm(qc, [0])


# ------------------------------------------------------------ the command line


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize(("folder", "job"), JOBS, ids=IDS)
def test_qasm_and_a_job_on_the_command_line_print_the_text_of_to_qasm(folder, job, script, monkeypatch, capsys):
    names = run_main(folder / script, ["--qasm", job["name"]], monkeypatch)
    assert capsys.readouterr().out == text_of(names, job["name"])


@pytest.mark.parametrize("script", SCRIPTS)
def test_qasm_and_a_job_not_in_the_script_stop_it_with_the_names_of_the_jobs(script, monkeypatch, capsys):
    with pytest.raises(SystemExit, match=r"^no job bell here; the jobs: X, BELL, BELL_AGAIN$"):
        run_main(EXAMPLES / "euroqexa-three-jobs" / script, ["--qasm", "BELL", "bell"], monkeypatch)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("script", SCRIPTS)
def test_qasm_with_no_job_prints_each_job_after_a_line_of_its_name(script, monkeypatch, capsys):
    names = run_main(EXAMPLES / "euroqexa-three-jobs" / script, ["--qasm"], monkeypatch)
    assert capsys.readouterr().out == "".join(f"// {job}\n" + text_of(names, job) for job in names["JOBS"])


def test_qrisps_qasm_outside_a_clone_stops_it_and_says_what_it_needs(tmp_path, monkeypatch, capsys):
    script = tmp_path / "emulate_qrisp.py"                                 # no folder above holds qrisp/qasm2.py
    script.write_bytes((EXAMPLES / "euroqexa-bell" / "emulate_qrisp.py").read_bytes())
    with pytest.raises(SystemExit, match=r"^--qasm needs examples/qrisp/qasm2\.py: run this file in its folder"):
        run_main(script, ["--qasm"], monkeypatch)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(("script", "line"), [("emulate_qutip.py", "QuTiP, run now, no noise"),
                                             ("emulate_qrisp.py", "Qrisp's emulator, run now, no noise")])
@pytest.mark.parametrize("folder", ["vlq-bell", "piastq-bell"])
def test_a_vlq_or_piastq_script_run_as_a_program_prints_a_line_per_job(folder, script, line, monkeypatch, capsys):
    run_main(EXAMPLES / folder / script, [], monkeypatch)
    stored = (qutip_stored if script == "emulate_qutip.py" else qrisp_stored)(EXAMPLES / folder)
    assert capsys.readouterr().out.splitlines() == [f"{name}: {line}  {top(stored[name])}" for name in stored] + [
        "Emulated on this computer: nothing was sent."]


# ------------------------------------------------------------ the scan list


def test_the_scripts_and_the_compile_of_a_qrisp_program_call_nothing_on_the_scan_list(monkeypatch):
    """Both scripts of a folder build, emulate and write each job, and its Qrisp program compiles and transpiles."""
    pytest.importorskip("qutip_qip")
    pytest.importorskip("qrisp")
    monkeypatch.syspath_prepend(str(EXAMPLES / "qrisp"))
    from programs import PROGRAMS

    folder = EXAMPLES / "qrisp" / "bell"
    in_qutip, in_qrisp = (runpy.run_path(str(folder / script)) for script in SCRIPTS)
    program = next(program for program in PROGRAMS if program.name == "BELL")
    with CalledModules() as called:
        for name, (build, read) in in_qutip["JOBS"].items():
            in_qutip["shares_of"](build(), read)
            text_of(in_qutip, name)
        for name, build in in_qrisp["JOBS"].items():
            in_qrisp["shares_of"](build())
            text_of(in_qrisp, name)
        program.circuit()                                  # Qrisp's compile, then qc.transpile()
    assert {hashlib.sha256(name).hexdigest() for name in (b"qutip", b"qrisp")} <= called.heads()   # it sees both run
    assert not called.heads() & {head for head, _, _ in BANNED}
