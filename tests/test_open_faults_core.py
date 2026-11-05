"""Small faults of the core of the app, each pinned by a test that failed before its fix.

A screen that cannot be written at the help, NaN in a record line and a saved read, shots and config numbers beyond
the floats, an error whose text cannot be read, a file in a folder that cannot be searched (with the path tests of
Python 3.14), the token filter made once for a value, a sum no row shows, the shot rule of the dry run and of a send
in one place, seconds below zero in an older record, and a Piast-Q shot that is not a list of bits.

Nine tests beside them guard what already held, and pass on 0.1.0 too: the four with stdout closed (`>&-`), as
sys.stdout is then None and argparse prints to stderr, a FIFO as a rules file and a job file, a rules file, job file
and record at a path with no file there (a link loop, a link below a file, a null byte), and the counts of Piast-Q
shots that are bits.
"""

import contextlib
import dataclasses
import errno
import io
import json
import math
import os
import signal
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from fakes import CONFIG, FakeClock, FakeSite, cfg, lines_of, places_in, records_of, send, write_manifest
from fakes.piastq import PAYLOAD

from qdevices import cli, config, monitor, record, redact, rulebook, rules, screen
from qdevices import manifest as manifests
from qdevices.dryrun import dry_run
from qdevices.saved_reads import SavedReads
from qdevices.sites import SITES
from qdevices.sites.base import SiteError
from qdevices.sites.facts import Key
from qdevices.sites.piastq import site as piastq

# --------------------------------------------------------------------- a screen that cannot be written

HELPS = [(["--help"], 0), (["--version"], 0), ([], 1), (["dry-run", "--help"], 0)]     # none reads the config


def app(args: list[str], **kw) -> subprocess.CompletedProcess:
    """`python -m qdevices ARGS` in a process of its own, with its stderr kept."""
    return subprocess.run([sys.executable, "-m", "qdevices", *args], stderr=subprocess.PIPE, text=True, check=False,
                          **kw)


def in_shell(line: str, args: list[str], **kw) -> subprocess.CompletedProcess:
    """`python -m qdevices ARGS` started by a shell line in which "$0" is Python: no Python code runs in a fork."""
    return subprocess.run(["/bin/sh", "-c", line, sys.executable, *args], stderr=subprocess.PIPE, text=True,
                          check=False, **kw)


@pytest.mark.parametrize(("args", "code"), HELPS)
def test_the_help_with_stdout_closed_ends_with_its_code_and_no_traceback(args, code):
    found = in_shell('exec "$0" -m qdevices "$@" >&-', args)
    assert found.returncode == code
    assert "Traceback" not in found.stderr and "Exception ignored" not in found.stderr


@pytest.mark.parametrize(("args", "code"), HELPS)
def test_the_help_into_a_pipe_whose_reader_is_gone_ends_with_its_code_and_nothing_on_stderr(args, code):
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        found = app(args, stdout=write_end)
    finally:
        os.close(write_end)
    assert (found.returncode, found.stderr) == (code, "")


@pytest.mark.parametrize(("args", "code"), HELPS)
def test_the_help_on_a_full_disk_ends_with_its_code_and_one_line_on_stderr_that_says_so(tmp_path, args, code):
    with (tmp_path / "screen.txt").open("w") as screen_file:      # Python ignores SIGXFSZ, so the write fails
        found = in_shell('ulimit -f 0; exec "$0" -m qdevices "$@"', args, stdout=screen_file)    # a file cannot grow
    error = f"OSError: [Errno {errno.EFBIG}] {os.strerror(errno.EFBIG)}"
    assert (found.returncode, found.stderr) == (code, f"the screen text could not all be written ({error})\n")


def test_the_end_of_a_command_puts_a_screen_that_cannot_be_written_on_the_null_device(monkeypatch):
    read_end, write_end = os.pipe()
    os.close(read_end)
    with open(write_end, "w", encoding="utf-8") as stream:
        stream.write("left on the screen\n")
        monkeypatch.setattr(sys, "stdout", stream)
        screen.finish()
        stream.write("more\n")
        stream.flush()                                  # a pipe with no reader would raise here
        assert stat.S_ISCHR(os.fstat(write_end).st_mode)


def test_the_end_of_a_command_passes_over_a_screen_that_is_closed_or_none(monkeypatch):
    closed = io.StringIO()
    closed.close()
    for stream in (closed, None):
        monkeypatch.setattr(sys, "stdout", stream)
        screen.finish()


# --------------------------------------------------------------------- NaN in a record line and a saved read

def strict(text: str) -> object:
    """A text read as standard JSON, which holds no NaN and no infinity."""
    def refuse(name: str):
        raise ValueError(f"{name} is not standard JSON")

    return json.loads(text, parse_constant=refuse)


def standard(text: str) -> list[dict]:
    """The lines of a record, each read as standard JSON."""
    return [strict(row) for row in text.splitlines() if row.strip()]


def test_a_record_line_holds_nan_and_the_infinities_as_texts_so_it_is_standard_json(tmp_path):
    path = tmp_path / "record.jsonl"
    with record.Record(path, FakeClock(), {"app": "qdevices"}) as rec:
        line = rec.write("rule", values=[math.nan, math.inf, -math.inf, 1.5], mean={"x": math.nan}, n=(math.inf,))
    (written,) = standard(path.read_text())
    assert (written["values"], written["mean"], written["n"]) == (["NaN", "Infinity", "-Infinity", 1.5],
                                                                 {"x": "NaN"}, ["Infinity"])
    assert math.isnan(line["values"][0])                # the line as this process made it


def test_a_verdict_that_holds_nan_reaches_the_record_in_standard_json(tmp_path, places, clock):
    def hook(job, state):
        return {"rule": "mine", "passed": True, "ratio": math.nan}

    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, FakeSite(), places, clock, max_order=1, user_rules={"before_job": hook}) == 0
    lines = standard(records_of(places)[0].read_text())
    assert [line["ratio"] for line in lines if line.get("rule") == "mine"] == ["NaN"]


def test_a_saved_read_holds_nan_and_the_infinities_as_texts_so_it_is_standard_json(tmp_path, clock):
    read = {"machine": "M1", "qubits": math.nan, "pending_jobs": math.inf, "pairs": [[0, -math.inf]]}
    written = strict(SavedReads(tmp_path / "reads").save(read, clock, lambda: []).read_text())
    assert (written["qubits"], written["pending_jobs"], written["pairs"]) == ("NaN", "Infinity", [[0, "-Infinity"]])


# --------------------------------------------------------------------- numbers beyond the floats

BIG = "1" + "0" * 400                 # a whole number that float() cannot hold


def test_a_dry_run_with_a_huge_negative_number_of_shots_fails_with_the_problem_of_the_manifest(tmp_path):
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("J1", -int(BIG)),))
    said: list[str] = []
    assert dry_run(m, cfg=cfg(), places=places_in(tmp_path), clock=FakeClock(), say=said.append) == 1
    assert "  FAILED: job 1: shots must be a whole number of 1 or more" in said


@pytest.mark.parametrize(("site", "key", "value"), [
    ("vlq", "award_hours", BIG), ("vlq", "budget_seconds", BIG), ("vlq", "job_seconds_limit", BIG),
    ("vlq", "wait_seconds", BIG), ("vlq", "wait_seconds", f"-{BIG}"), ("vlq", "max_shots", BIG),
    ("piastq", "site_max_shots", BIG)])
def test_a_config_number_beyond_the_floats_is_refused(site, key, value):
    with pytest.raises(config.ConfigError) as refused:
        config.parse(f"[{site}]\n{key} = {value}\n")
    assert str(refused.value) == f"[{site}] {key} must be a finite number"


def test_a_config_number_of_more_digits_than_python_reads_is_refused():
    with pytest.raises(config.ConfigError) as refused:
        config.parse(f"[vlq]\nwait_seconds = {'1' * 5000}\n")
    assert str(refused.value) == "the config holds a whole number of more digits than can be read"


def test_usage_with_an_award_beyond_the_floats_is_refused_at_the_command_line(tmp_path, capsys):
    places = places_in(tmp_path)
    places.config.write_text(CONFIG.replace("[vlq]\n", f"[vlq]\naward_hours = {BIG}\n"))
    assert cli.main(["usage"], places=places, environ={}) == 1
    assert capsys.readouterr().out == "REFUSED: [vlq] award_hours must be a finite number\n"


def test_a_key_of_the_config_refuses_a_whole_number_beyond_the_floats_as_it_refuses_an_infinity():
    key = Key(name="budget_seconds", kind=(int, float), least=0)
    assert [key.problem(value) for value in (int(BIG), -int(BIG), math.inf, 10 ** 300, -1)] == [
        "must be a finite number", "must be a finite number", "must be a finite number", None, "must be 0 or more"]


@pytest.mark.parametrize(("shots", "problem"), [
    (1, None), (manifests.MOST_SHOTS, None), (0, "shots must be a whole number of 1 or more"),
    (True, "shots must be a whole number of 1 or more"), (2.0, "shots must be a whole number of 1 or more"),
    (-int(BIG), "shots must be a whole number of 1 or more"),
    (manifests.MOST_SHOTS + 1, "shots must be at most 1,000,000,000")])
def test_the_shot_rule_of_a_manifest_is_written_once_for_its_reader_and_the_dry_run(shots, problem):
    assert (manifests.shot_problem(shots), manifests.takes_shots(shots)) == (problem, problem is None)


# --------------------------------------------------------------------- an error whose text cannot be read

class Unreadable(ValueError):
    """An error whose text cannot be read: str() of it raises."""

    def __str__(self) -> str:
        raise RuntimeError("no text")


class UnreadableExit(ValueError):
    """An error whose str() raises SystemExit."""

    def __str__(self) -> str:
        raise SystemExit(4)


@pytest.mark.parametrize("error", [Unreadable, UnreadableExit])
def test_a_hook_whose_error_has_no_readable_text_is_a_failed_verdict_and_nothing_is_sent(tmp_path, places, clock,
                                                                                         error):
    def hook(job, state):
        raise error()

    site = FakeSite()
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, site, places, clock, max_order=1, user_rules={"before_job": hook}) == 2
    stop = lines_of(records_of(places)[0])[-1]
    assert (stop["event"], stop["kind"], stop["reason"]) == (
        "stop", "rule", f"rule before_job: the hook before_job raised {error.__name__} (its text cannot be read)")
    assert [call for call in site.calls if call[0] == "submit"] == []


def test_a_rules_file_that_raises_an_error_with_no_readable_text_is_refused(tmp_path):
    path = tmp_path / "rules.py"
    path.write_text("class Bad(Exception):\n    def __str__(self):\n        raise RuntimeError('no text')\n\n\n"
                    "raise Bad()\n")
    with pytest.raises(rulebook.RuleFileError) as refused:
        rulebook.load(path)
    assert str(refused.value) == f"the rules file {path} cannot be loaded: Bad (its text cannot be read)"


class _ReadBreaks(FakeSite):
    """A site whose read of the machine fails with an error of the program whose text cannot be read."""

    def read(self) -> dict:
        raise Unreadable()


def test_an_error_of_the_program_with_no_readable_text_still_ends_in_its_stop_line_and_exit_3(tmp_path, places,
                                                                                              clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, _ReadBreaks(), places, clock, max_order=1) == 3
    stop = lines_of(records_of(places)[0])[-1]
    assert (stop["event"], stop["kind"], stop["reason"]) == (
        "stop", "error", "an error of the program: Unreadable (its text cannot be read)")


# --------------------------------------------------------------------- a file in a folder that cannot be searched

@contextlib.contextmanager
def unsearchable(folder: Path, *files: str):
    """The folder, with these files in it, made one that cannot be searched while the block runs; then searchable."""
    if os.geteuid() == 0:
        pytest.skip("root can search any folder")
    folder.mkdir()
    for name in files:
        (folder / name).touch()
    folder.chmod(0o600)                   # read and write, no search
    try:
        yield folder
    finally:
        folder.chmod(0o700)


@pytest.fixture
def python_3_14(monkeypatch):
    """Path.exists, is_file and is_dir as Python 3.14 has them: False at any OSError, as the tests of os.path give."""
    for name, test in (("exists", os.path.exists), ("is_file", os.path.isfile), ("is_dir", os.path.isdir)):
        monkeypatch.setattr(Path, name, lambda self, test=test: test(self))


def test_a_config_in_a_folder_that_cannot_be_searched_is_refused_at_the_command_line(tmp_path, capsys, python_3_14):
    places = dataclasses.replace(places_in(tmp_path), config=tmp_path / "shut" / "qdevices.toml")
    with unsearchable(places.config.parent, "qdevices.toml"):
        with pytest.raises(config.ConfigError) as refused:
            config.load(places.config)
        assert cli.main(["runs"], places=places, environ={}) == 1
    assert str(refused.value) == f"{places.config} cannot be read: [Errno 13] Permission denied: '{places.config}'"
    assert capsys.readouterr().out == f"REFUSED: {refused.value}\n"


def test_a_rules_file_in_a_folder_that_cannot_be_searched_is_refused(tmp_path, python_3_14):
    with unsearchable(tmp_path / "shut", "rules.py") as folder, pytest.raises(rulebook.RuleFileError) as refused:
        rulebook.load(folder / "rules.py")
    assert str(refused.value) == f"the rules file {tmp_path / 'shut' / 'rules.py'} cannot be read: PermissionError"


def test_a_job_file_linked_into_a_folder_that_cannot_be_searched_is_a_problem_of_the_manifest(tmp_path, python_3_14):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    (m.parent / "J1.qasm").unlink()
    (m.parent / "J1.qasm").symlink_to(tmp_path / "shut" / "J1.qasm")
    with unsearchable(tmp_path / "shut", "J1.qasm"):
        _man, problems = manifests.read(m, SITES)
    assert problems == [f"job 1: the file {m.parent / 'J1.qasm'} cannot be read: PermissionError"]


def test_a_record_in_a_folder_that_cannot_be_searched_is_refused_by_jobs_and_shown_by_runs(tmp_path, capsys,
                                                                                         python_3_14):
    rec, places = tmp_path / "shut" / "run_20260105T120000Z.jsonl", places_in(tmp_path)
    with unsearchable(rec.parent, rec.name):
        assert cli.main(["jobs", str(rec)], places=places, environ={}) == 1
        assert cli.main(["runs", str(rec)], places=places, environ={}) == 0
    error = f"{rec} cannot be read: PermissionError"
    assert capsys.readouterr().out == f"REFUSED: {error}\n{rec}: {error}\n"


def test_a_fifo_is_no_rules_file_and_no_job_file_and_is_never_opened(tmp_path):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    (m.parent / "J1.qasm").unlink()
    os.mkfifo(m.parent / "J1.qasm")
    os.mkfifo(tmp_path / "rules.py")
    earlier = signal.signal(signal.SIGALRM, lambda *_: pytest.fail("a FIFO with no writer was opened"))
    signal.alarm(5)                       # an open of a FIFO with no writer would wait for ever
    try:
        with pytest.raises(rulebook.RuleFileError) as refused:
            rulebook.load(tmp_path / "rules.py")
        _man, problems = manifests.read(m, SITES)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, earlier)
    assert str(refused.value) == f"no rules file at {tmp_path / 'rules.py'}"
    assert problems == [f"job 1: there is no file {m.parent / 'J1.qasm'}"]


def no_file_at(folder: Path, name: str, case: str) -> Path:
    """A path where Path.stat finds no file: a link to itself, a link below a file, or a name with a null byte."""
    if case == "null byte":
        return folder / name.replace(".", chr(0) + ".", 1)
    (folder / "a-file").touch()
    path = folder / name
    path.symlink_to(path if case == "link loop" else folder / "a-file" / name)
    return path


@pytest.mark.parametrize("case", ["link loop", "link below a file", "null byte"])
def test_a_path_with_no_file_there_is_no_rules_file_no_job_file_and_no_record(tmp_path, case):
    rules, rec = no_file_at(tmp_path, "rules.py", case), no_file_at(tmp_path, "run_20260105T120000Z.jsonl", case)
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    (m.parent / "J1.qasm").unlink()
    job = no_file_at(m.parent, "J1.qasm", case)
    m.write_text(m.read_text().replace('"J1.qasm"', json.dumps(job.name)))
    with pytest.raises(rulebook.RuleFileError) as no_rules:
        rulebook.load(rules)
    with pytest.raises(record.RecordError) as no_record:
        record.RecordLines.read(rec)
    assert (str(no_rules.value), str(no_record.value)) == (f"no rules file at {rules}", f"no record at {rec}")
    assert manifests.read(m, SITES)[1] == [f"job 1: there is no file {job}"]


# --------------------------------------------------------------------- the token filter, made once

def test_the_token_filter_of_a_value_makes_the_forms_of_each_secret_once(monkeypatch):
    made: list[str] = []
    forms = redact._forms
    monkeypatch.setattr(redact, "_forms", lambda secret: made.append(secret) or forms(secret))
    value = {"a": ["x secret-0001 y", "z"], "b": {"c": "secret-0001"}, "secret-0001": 1}
    assert redact.redact_all(value, ["secret-0001"]) == {"a": ["x [hidden] y", "z"], "b": {"c": "[hidden]"},
                                                        "[hidden]": 1}
    assert made == ["secret-0001"]


# --------------------------------------------------------------------- the sums of usage

def test_every_sum_of_the_usage_totals_is_shown_in_its_row():
    totals = monitor._Totals()
    names = [f.name for f in dataclasses.fields(totals)]
    for number, name in enumerate(names, 101):
        setattr(totals, name, number)
    row = totals.row("site", "project")
    assert [name for number, name in enumerate(names, 101) if str(number) not in row] == []


# --------------------------------------------------------------------- the shot rule in one place

def test_the_dry_run_judges_the_shots_of_each_job_by_the_shot_rule_of_a_send(tmp_path, monkeypatch):
    judged: list = []
    rule = rules.shot_limit

    def kept(job: dict, state: dict) -> dict:
        judged.append((job["order"], state))
        return rule(job, state)

    monkeypatch.setattr(rules, "shot_limit", kept)
    conf = cfg(CONFIG.replace("[piastq]\n", "[piastq]\nsite_max_shots = 400\nmax_shots = 450\n"))
    m = write_manifest(tmp_path / "m", site="piastq", jobs=(("P1", 100), ("P2", 500)), text=PAYLOAD)
    said: list[str] = []
    assert dry_run(m, cfg=conf, places=places_in(tmp_path), clock=FakeClock(), say=said.append) == 1
    limits = {"site_max_shots": 400, "max_shots": 450}
    assert judged == [(1, limits), (2, limits)]
    failed = [line for line in said if line.startswith("  FAILED")]
    assert failed == ["  FAILED: order 2 (P2): 500 shots, the limit is 400"]


# --------------------------------------------------------------------- a time below zero in an older record

def screens(places, capsys, *commands: list[str]) -> dict[str, str]:
    """What each command of the app prints, by its name, each ending with exit code 0."""
    shown = {}
    for args in commands:
        assert cli.main(args, places=places, environ={}) == 0
        shown[args[0]] = capsys.readouterr().out
    return shown


@pytest.mark.parametrize(("wall", "runs", "jobs", "usage", "budget"), [
    (None, "0.0 s measured; 1 results with no seconds", "-", ["0.0", "0.0"], 100.0),     # job_seconds_limit
    (7.5, "7.5 s measured", "7.500", ["7.5", "7.5"], 7.5),
], ids=["no-wall-seconds", "wall-seconds"])
def test_a_result_line_of_0_1_0_with_seconds_below_zero_is_no_measure(tmp_path, places, clock, capsys, wall, runs,
                                                                     jobs, usage, budget):
    assert send(write_manifest(tmp_path / "old", jobs=(("J1", 10),)), FakeSite(), places, clock, max_order=1) == 0
    (rec,) = records_of(places)
    rows = [{**row, "seconds": -3599.0, "wall_seconds": wall} if row["event"] == "result" else row
            for row in lines_of(rec)]       # as 0.1.0 wrote a Euro-Q-Exa result whose stamps ran backwards
    rec.write_text("".join(json.dumps(row) + "\n" for row in rows))
    places.config.write_text(CONFIG)
    shown = screens(places, capsys, ["runs"], ["jobs", str(rec)], ["usage"])
    assert f"1 results of 1 jobs; {runs}; " in shown["runs"] and "-3599" not in "".join(shown.values())
    assert [row.split()[-1] for row in shown["jobs"].splitlines() if row.split()[:1] == ["1"]] == [jobs]
    assert [row.split()[5:7] for row in shown["usage"].splitlines() if row.startswith("euroqexa ")] == [usage]
    assert send(write_manifest(tmp_path / "new", jobs=(("J1", 10),)), FakeSite(), places, clock, max_order=1) == 0
    (new,) = [path for path in records_of(places) if path.parent.name == "new"]
    assert [line["used_seconds"] for line in lines_of(new) if line.get("rule") == "budget"] == [budget]


# --------------------------------------------------------------------- a Piast-Q shot that is not bits

@pytest.mark.parametrize("shot", [[], [2, 0], [-1, 0], [0.5, 1], [1.9, 0], [1.0, 0], [True, 0], ["1", 0]],
                         ids=["empty", "two", "minus-one", "half", "near-two", "float-one", "true", "text"])
def test_a_piastq_shot_that_is_not_a_list_of_the_ints_0_and_1_is_no_list_of_bits(shot):
    with pytest.raises(SiteError) as raised:
        piastq._counts({"result": [[0, 1], shot]})
    assert (str(raised.value), raised.value.step) == ("a shot of the result is not a list of bits", "result")


def test_piastq_shots_of_the_ints_0_and_1_give_the_counts_in_the_order_first_seen():
    assert piastq._counts({"result": [[0, 1], [1, 1], [0, 1]]}) == {"01": 2, "11": 1}
