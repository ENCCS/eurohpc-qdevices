"""The --qasm of each Euro-Q-Exa script: the OpenQASM 2 text that QuTiP and Qrisp code give, read back and compared.

The texts are read by the parser of the examples and must give the shares of the text that was sent. Qrisp's, through
examples/qrisp/qasm2.py, gives the same bytes as the text sent, but for INVERSE: there crz is built from rz and cx,
the register meas is written c, and the barrier is left out. The tests of the arguments write the scripts of a folder
again in tmp_path, by the writers, and run them as the program, with python, by a link and with python -m, and as a
notebook runs them: by runpy, as Choose one does, with the arguments that %run gives, and pasted in a cell, also after
a %run -i of another file. They also run a script with no sys.orig_argv, as on Python 3.9: as the program, and as text
with a __file__ and an empty sys.argv. They run it by runpy or pasted in a terminal IPython or in a kernel started by
path too. The last test watches these paths for a call to a module on the scan list of test_scan.py.
"""

import hashlib
import importlib
import re
import runpy
import shutil
import subprocess
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
    """A script run as the program, with these arguments after its name; the names it holds at the end.

    The command line, sys.orig_argv, ends with sys.argv, as when python runs the file itself.
    """
    pytest.importorskip(SCRIPTS[script.name])
    monkeypatch.setattr(sys, "argv", [str(script), *argv])
    monkeypatch.setattr(sys, "orig_argv", [sys.executable, str(script), *argv])
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


# ------------------------------------------------------------ the arguments, of the scripts the writers write now

SITES = ["euroqexa-three-jobs", "vlq-bell", "piastq-bell"]
KERNEL = (["/x/ipykernel_launcher.py", "-f", "/x/kernel-1.json"],                # sys.argv in a Jupyter kernel
          ["/x/python", "-m", "ipykernel_launcher", "-f", "/x/kernel-1.json"])   # and the command line of the kernel
# The sys.argv and command line of each host that runs a script by runpy or has it pasted in: a kernel as Jupyter starts
# it, with -m, a kernel started by path, and a terminal IPython started with options. In the last two the command line
# ends with sys.argv, as a real kernel and IPython show.
HOSTS = {"kernel": KERNEL, "kernel-by-path": (KERNEL[0], ["/x/python", *KERNEL[0]]),
         "ipython": (["/x/ipython", "--no-banner", "--colors=nocolor"],
                     ["/x/python", "/x/ipython", "--no-banner", "--colors=nocolor"])}
STOPS = {"vlq-bell": "--qasm is for the folders of Euro-Q-Exa; VLQ takes OpenQASM 3 in its own gates r, cz and move",
         "piastq-bell": "--qasm is for the folders of Euro-Q-Exa; Piast-Q takes the broker's list of RZ, R and RXX"}
SAID = {"emulate_qutip.py": "QuTiP, run now, no noise", "emulate_qrisp.py": "Qrisp's emulator, run now, no noise"}
WRITERS = {"emulate_qutip.py": "write_qutip_scripts", "emulate_qrisp.py": "write_qrisp_scripts"}


def written(tmp_path: Path, name: str, script: str) -> Path:
    """The script of a copy of the folder `name`, as its writer writes it now; examples/qrisp/qasm2.py above it."""
    pytest.importorskip(SCRIPTS[script])
    root, folder = tmp_path / "examples", EXAMPLES / name
    (root / "qrisp").mkdir(parents=True, exist_ok=True)
    (root / name).mkdir(parents=True, exist_ok=True)
    shutil.copy(EXAMPLES / "qrisp" / "qasm2.py", root / "qrisp" / "qasm2.py")
    for file in ("manifest.json", *{job["file"] for job in jobs_of(folder)}):
        shutil.copy(folder / file, root / name / file)
    path = root / name / script
    path.write_text(importlib.import_module(WRITERS[script]).script_text(root / name, root), encoding="utf-8")
    return path


def loop_lines(name: str, script: str) -> list:
    """What a script prints with no argument: a line for each job, by the stored shares of the folder."""
    stored = (qutip_stored if script == "emulate_qutip.py" else qrisp_stored)(EXAMPLES / name)
    return [f"{job}: {SAID[script]}  {top(stored[job])}" for job in stored] + [
        "Emulated on this computer: nothing was sent."]


def usage_of(name: str, script: str) -> str:
    return f"usage: python {script}" + (" [--qasm [JOB ...]]" if name.startswith("euroqexa") else "")


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("name", SITES)
def test_with_no_argument_a_script_prints_a_line_for_each_job(name, script, tmp_path, monkeypatch, capsys):
    run_main(written(tmp_path, name, script), [], monkeypatch)
    assert capsys.readouterr().out.splitlines() == loop_lines(name, script)


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("argv", [["--qasm", "BELL"], ["--qasm"]], ids=["one-job", "every-job"])
def test_qasm_in_a_folder_of_euroqexa_prints_the_text_of_to_qasm(argv, script, tmp_path, monkeypatch, capsys):
    names = run_main(written(tmp_path, "euroqexa-three-jobs", script), argv, monkeypatch)
    jobs = argv[1:] or list(names["JOBS"])
    assert capsys.readouterr().out == "".join(
        ("" if len(jobs) == 1 else f"// {job}\n") + text_of(names, job) for job in jobs)


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("argv", [["--qasm"], ["--qasm", "BELL"]], ids=["alone", "with-a-job"])
@pytest.mark.parametrize("name", STOPS)
def test_qasm_in_a_folder_of_vlq_or_piastq_stops_and_says_what_the_site_takes(name, argv, script, tmp_path,
                                                                              monkeypatch, capsys):
    with pytest.raises(SystemExit, match=rf"^{re.escape(STOPS[name])}$"):
        run_main(written(tmp_path, name, script), argv, monkeypatch)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("argv", [["--qasn"], ["-h"], ["BELL"], ["BELL", "--qasm"]],
                         ids=["misspelt", "help", "a-job-alone", "qasm-second"])
@pytest.mark.parametrize("name", SITES)
def test_any_other_argument_stops_a_script_with_its_usage(name, argv, script, tmp_path, monkeypatch, capsys):
    with pytest.raises(SystemExit, match=rf"^{re.escape(usage_of(name, script))}$"):
        run_main(written(tmp_path, name, script), argv, monkeypatch)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("name", SITES)
def test_run_by_runpy_as_choose_one_does_a_script_leaves_the_arguments_of_its_host_alone(name, script, host, tmp_path,
                                                                                         monkeypatch, capsys):
    """As Choose one runs it: runpy, which sets sys.argv[0] to the script and keeps the host's own arguments."""
    path = written(tmp_path, name, script)
    monkeypatch.setattr(sys, "argv", list(HOSTS[host][0]))
    monkeypatch.setattr(sys, "orig_argv", list(HOSTS[host][1]))
    runpy.run_path(str(path), run_name="__main__")
    assert capsys.readouterr().out.splitlines() == loop_lines(name, script)
    assert sys.argv == HOSTS[host][0]


def test_choose_one_runs_both_scripts_of_a_folder_as_before(tmp_path, monkeypatch, capsys):
    from scripts_shown import show_scripts

    for script in SCRIPTS:
        written(tmp_path, "euroqexa-three-jobs", script)
    monkeypatch.setattr(sys, "argv", list(KERNEL[0]))
    monkeypatch.setattr(sys, "orig_argv", list(KERNEL[1]))
    show_scripts(tmp_path / "examples" / "euroqexa-three-jobs")
    out = capsys.readouterr().out.splitlines()
    assert all(line in out for script in SCRIPTS for line in loop_lines("euroqexa-three-jobs", script))


@pytest.mark.parametrize(("name", "script", "argv"), [
    ("euroqexa-three-jobs", "emulate_qutip.py", ["--qasm", "BELL"]), ("euroqexa-three-jobs", "emulate_qutip.py", []),
    ("euroqexa-three-jobs", "emulate_qutip.py", ["--qasn"]), ("vlq-bell", "emulate_qutip.py", ["--qasm"]),
    ("piastq-bell", "emulate_qrisp.py", ["--qasm"])], ids=["qasm-job", "none", "misspelt", "vlq-qasm", "piastq-qasm"])
def test_run_by_python_in_its_folder_a_script_reads_its_own_arguments(name, script, argv, tmp_path):
    """The command of the README, with nothing in place of sys.argv: python emulate_qutip.py in the folder."""
    path = written(tmp_path, name, script)
    done = subprocess.run([sys.executable, script, *argv], cwd=path.parent, capture_output=True, text=True,
                          check=False)
    if argv == ["--qasm", "BELL"]:
        assert (done.returncode, done.stderr, done.stdout) == (0, "", text_of(runpy.run_path(str(path)), "BELL"))
    elif not argv:
        assert (done.returncode, done.stderr, done.stdout.splitlines()) == (0, "", loop_lines(name, script))
    else:
        said = usage_of(name, script) if argv == ["--qasn"] else STOPS[name]
        assert (done.returncode, done.stderr, done.stdout) == (1, said + "\n", "")


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("argv", [["--qasn"], ["--qasm", "BELL"]], ids=["misspelt", "qasm-job"])
def test_run_by_python_through_a_link_a_script_reads_its_own_arguments(argv, script, tmp_path):
    """python LINK, in another folder: sys.argv[0] and __file__ are the link, which names the file of the script."""
    path, elsewhere = written(tmp_path, "euroqexa-three-jobs", script), tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "mine.py").symlink_to(path)
    done = subprocess.run([sys.executable, "mine.py", *argv], cwd=elsewhere, capture_output=True, text=True,
                          check=False)
    if argv == ["--qasn"]:
        assert (done.returncode, done.stderr, done.stdout) == (1, usage_of("euroqexa-three-jobs", script) + "\n", "")
    else:
        assert (done.returncode, done.stderr, done.stdout) == (0, "", text_of(runpy.run_path(str(path)), "BELL"))


@pytest.mark.parametrize("name", ["euroqexa-three-jobs", "vlq-bell"])
def test_run_by_python_m_in_its_folder_a_script_reads_a_first_qasm(name, tmp_path):
    """python -m emulate_qutip: sys.argv[0] is the path of the file, while the command line names the module."""
    path = written(tmp_path, name, "emulate_qutip.py")
    done = subprocess.run([sys.executable, "-m", "emulate_qutip", "--qasm", "BELL"], cwd=path.parent,
                          capture_output=True, text=True, check=False)
    if name in STOPS:
        assert (done.returncode, done.stderr, done.stdout) == (1, STOPS[name] + "\n", "")
    else:
        assert (done.returncode, done.stderr, done.stdout) == (0, "", text_of(runpy.run_path(str(path)), "BELL"))


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("argv", [[], ["--qasn"], ["--qasm", "BELL"]], ids=["none", "misspelt", "qasm-job"])
def test_with_no_orig_argv_as_on_python_3_9_a_script_reads_only_a_first_qasm(argv, script, tmp_path, monkeypatch,
                                                                              capsys):
    """Python 3.9 has no sys.orig_argv: run as the program, a script runs its loop but for a first --qasm, as before."""
    path = written(tmp_path, "euroqexa-three-jobs", script)
    monkeypatch.setattr(sys, "argv", [str(path), *argv])
    monkeypatch.delattr(sys, "orig_argv")
    names = runpy.run_path(str(path), run_name="__main__")
    if argv[:1] == ["--qasm"]:
        assert capsys.readouterr().out == text_of(names, "BELL")
    else:
        assert capsys.readouterr().out.splitlines() == loop_lines("euroqexa-three-jobs", script)


@pytest.mark.parametrize("script", SCRIPTS)
def test_with_an_empty_argv_and_no_orig_argv_a_script_runs_its_loop(script, tmp_path, monkeypatch, capsys):
    """A host that empties sys.argv and runs the text with a __file__, with no sys.orig_argv: the loop, as before."""
    path = written(tmp_path, "euroqexa-three-jobs", script)
    monkeypatch.setattr(sys, "argv", [])
    monkeypatch.delattr(sys, "orig_argv")
    names = {"__name__": "__main__", "__file__": str(path)}
    exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), names)
    assert capsys.readouterr().out.splitlines() == loop_lines("euroqexa-three-jobs", script)


@pytest.mark.parametrize("script", SCRIPTS)
@pytest.mark.parametrize("name", ["euroqexa-three-jobs", "vlq-bell"])
def test_run_by_a_notebook_with_qasm_first_a_script_reads_it(name, script, tmp_path, monkeypatch, capsys):
    """As %run emulate_qutip.py --qasm BELL runs it: sys.argv holds the arguments, the command line is the kernel's."""
    path = written(tmp_path, name, script)
    monkeypatch.setattr(sys, "argv", [str(path), "--qasm", "BELL"])
    monkeypatch.setattr(sys, "orig_argv", list(KERNEL[1]))
    if name in STOPS:
        with pytest.raises(SystemExit, match=rf"^{re.escape(STOPS[name])}$"):
            runpy.run_path(str(path), run_name="__main__")
        assert capsys.readouterr().out == ""
    else:
        names = runpy.run_path(str(path), run_name="__main__")
        assert capsys.readouterr().out == text_of(names, "BELL")


@pytest.mark.parametrize("run_i", [False, True], ids=["alone", "after-run-i"])
@pytest.mark.parametrize("host", HOSTS)
@pytest.mark.parametrize("script", SCRIPTS)
def test_pasted_in_a_cell_a_script_runs_its_loop_however_its_host_was_started(script, host, run_i, tmp_path,
                                                                              monkeypatch, capsys):
    """The text of a script in a cell: sys.argv and the command line are the host's own, and no file is run.

    After a %run -i of another file, the namespace of the cell holds the __file__ of that file, as IPython 9 leaves it.
    """
    path, other = written(tmp_path, "euroqexa-three-jobs", script), tmp_path / "setup.py"
    other.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", list(HOSTS[host][0]))
    monkeypatch.setattr(sys, "orig_argv", list(HOSTS[host][1]))
    names = {"__name__": "__main__", **({"__file__": str(other)} if run_i else {})}
    exec(compile(path.read_text(encoding="utf-8"), "<cell>", "exec"), names)
    assert capsys.readouterr().out.splitlines() == loop_lines("euroqexa-three-jobs", script)


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
