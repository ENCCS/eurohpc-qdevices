"""Edges of the command line, check and the dry run that no other test pins, each reached through one helper."""

import argparse
import importlib.metadata
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fakes import CONFIG, TOKEN, FakeClock, FakeSite, cfg, write_manifest

from qdevices import __version__, check, cli, dryrun

READ = {"read_at": "2026-01-05T11:00:00+00:00", "machine": "M1", "qubits": 5}


def main(places, *args, environ=None) -> int:
    """`qdevices ARGS` with the config of the tests and a fake site: the exit code."""
    places.config.write_text(CONFIG)
    clock = FakeClock()
    return cli.main(list(map(str, args)), places=places, environ={} if environ is None else environ, clock=clock,
                    sleep=clock.sleep, make_site=lambda *a, **k: FakeSite(), host="host-a")


def dry(path, places, clock, **kw) -> tuple[int, list[str]]:
    """The dry run of a manifest: its exit code and its lines."""
    out = []
    code = dryrun.dry_run(path, cfg=cfg(), places=places, clock=clock, say=out.append, **kw)
    return code, out


def live(places, clock, read: dict) -> tuple[int, list[str]]:
    """`check euroqexa --live` with a fake site that reads `read`: the exit code and its lines."""
    out = []
    code = check.check("euroqexa", live=True, token=TOKEN, manifest_path=None, cfg=cfg(), places=places,
                       clock=clock, sleep=clock.sleep, host="host-a", make_site=lambda *a, **k: FakeSite(read=read),
                       say=out.append)
    return code, out


def save(places, name: str, text: str) -> Path:
    """A file in the folder where `check --live` stores the reads of Euro-Q-Exa."""
    folder = places.reads / "euroqexa"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text)
    return folder / name


@pytest.mark.parametrize("kind", ["missing", "folder"])
def test_jobs_of_a_record_that_is_not_there_is_refused(capsys, places, tmp_path, kind):
    record = tmp_path / "r.jsonl"
    if kind == "folder":
        record.mkdir()
    assert (main(places, "jobs", record), capsys.readouterr().out) == (1, f"REFUSED: no record at {record}\n")


@pytest.mark.parametrize("text", [None, "{not json", "[1, 2"])
def test_a_read_given_with_read_that_is_not_json_fails_the_dry_run_at_once(tmp_path, places, clock, text):
    given = tmp_path / "given.json"
    if text is not None:
        given.write_text(text)
    assert dry(write_manifest(tmp_path / "m"), places, clock, read_file=given) == (1, [
        "Dry run: no network call, no token.", f"  FAILED: {given} cannot be read as JSON"])


def test_a_newest_read_that_is_not_json_is_passed_over_for_an_older_one(tmp_path, places, clock):
    older = save(places, "read_20260105T110000Z.json", json.dumps(READ))
    save(places, "read_20260105T113000Z.json", "{cut")
    code, out = dry(write_manifest(tmp_path / "m"), places, clock)
    assert code == 0 and out[4] == f"  read      {older}, 1.0 hours old"


@pytest.mark.parametrize("read_at", [None, "yesterday", "2026-01-05T10:00:00", 7, ["2026-01-05T10:00:00+00:00"]])
def test_a_read_whose_time_cannot_be_read_has_an_age_not_known_and_no_note(tmp_path, places, clock, read_at):
    read = {**READ, "read_at": read_at} if read_at is not None else {k: v for k, v in READ.items() if k != "read_at"}
    file = save(places, "read_20260105T110000Z.json", json.dumps(read))
    for given in (None, file):
        code, out = dry(write_manifest(tmp_path / f"m{given is None}"), places, clock, read_file=given)
        assert code == 0 and out[4] == f"  read      {file}, age not known"
        assert out[5] == "  plan"


def test_check_takes_the_token_out_of_the_environment_offline_and_live(places):
    for args in (("check", "euroqexa"), ("check", "euroqexa", "--live")):
        environ = {"MQSS_TOKEN": TOKEN, "OTHER": "x"}
        assert main(places, *args, environ=environ) == 0
        assert environ == {"OTHER": "x"}


def test_the_stored_read_starts_with_read_at_and_stores_other_values_as_text(places, clock):
    stored = places.reads / "euroqexa" / "read_20260105T120000Z.json"
    read = {"machine": "M1", "read_at": "its own", "when": datetime(2026, 1, 2, tzinfo=UTC), "path": Path("a")}
    assert live(places, clock, read)[0] == 0                   # a read_at of the read replaces the time, in first place
    assert stored.read_text(encoding="utf-8") == ('{\n "read_at": "its own",\n "machine": "M1",\n'
                                                  ' "when": "2026-01-02 00:00:00+00:00",\n "path": "a"\n}\n')
    assert live(places, clock, {"machine": "M2"})[0] == 0      # in the same second, a second read replaces the file
    assert stored.read_text(encoding="utf-8") == '{\n "read_at": "2026-01-05T12:00:00+00:00",\n "machine": "M2"\n}\n'


@pytest.mark.parametrize("machine", ["", None, 0])
def test_a_read_that_names_no_machine_is_stored_as_a_list(places, clock, machine):
    code, out = live(places, clock, {"machine": machine})
    files = [p.name for p in (places.reads / "euroqexa").iterdir()]
    assert code == 0 and files == ["list_20260105T120000Z.json"]
    assert out[-1] == f"List of the machines stored in {places.reads / 'euroqexa' / files[0]}. No job was made."


def test_the_console_script_is_the_main_of_the_command_line():
    found = importlib.metadata.entry_points(group="console_scripts", name="qdevices")
    assert [entry.value for entry in found] == ["qdevices.cli:main"]
    assert next(iter(found)).load() is cli.main


def test_python_m_qdevices_runs_the_command_line(tmp_path):
    done = subprocess.run([sys.executable, "-m", "qdevices", "--version"], capture_output=True, text=True,
                          cwd=tmp_path, timeout=60, check=False)
    assert (done.returncode, done.stdout, done.stderr) == (0, f"qdevices {__version__}\n", "")


def test_each_command_of_the_parser_has_its_method_and_each_method_its_command():
    sub = next(action for action in cli.parser()._actions if isinstance(action, argparse._SubParsersAction))
    methods = sorted(name[3:].replace("_", "-") for name in dir(cli.Commands) if name.startswith("do_"))
    assert sorted(sub.choices) == methods and len(methods) == 9


class Logged(FakeClock):
    """A fake clock that adds each read of the time to `log`."""

    def __init__(self, log: list) -> None:
        super().__init__()
        self.log = log

    def utc(self):
        self.log.append("utc")
        return super().utc()


def test_check_live_reads_the_secrets_last_after_the_folder_and_the_two_times_of_the_file(places):
    log = []

    class Site(FakeSite):
        def secrets(self) -> list[str]:
            log.append(("secrets", (places.reads / "euroqexa").is_dir(), len(log)))
            return super().secrets()

    clock = Logged(log)
    assert check.check("euroqexa", live=True, token=TOKEN, manifest_path=None, cfg=cfg(), places=places, clock=clock,
                       sleep=clock.sleep, host="host-a", make_site=lambda *a, **k: Site(), say=lambda line: None) == 0
    assert log == ["utc", "utc", "utc", ("secrets", True, 3)]


@pytest.mark.parametrize("saved", [False, True])
def test_the_dry_run_reads_the_clock_once_with_or_without_a_saved_read(tmp_path, places, saved):
    if saved:
        save(places, "read_20260105T110000Z.json", json.dumps(READ))
    log = []
    assert dry(write_manifest(tmp_path / "m"), places, Logged(log))[0] == 0
    assert log == ["utc"]
