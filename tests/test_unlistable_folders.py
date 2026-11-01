"""A folder below an older record folder that cannot be listed, and a place or a record whose stat is refused.

Each gives an error line in `runs` and refuses a send: no record drops out without a word, and no traceback.
"""

import json
import os
from pathlib import Path

import pytest
from fakes import CONFIG, FakeClock, FakeSite, cfg, places_in, send, write_manifest

from qdevices import cli, monitor, runner

OPEN = [{"event": "submitting", "order": 1, "name": "K1"},
        {"event": "submitted", "order": 1, "name": "K1", "uuid": "u-9"}]


def write(path: Path) -> Path:
    """A record with an open order, which blocks a start once it is read."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in OPEN))
    return path


def refuse_stat(monkeypatch, path: Path) -> None:
    """Path.is_file of `path` raises PermissionError, as in a folder that can be listed but not searched."""
    is_file = Path.is_file

    def denied(self):
        if self == path:
            raise PermissionError(13, "Permission denied", str(self))
        return is_file(self)

    monkeypatch.setattr(Path, "is_file", denied)


def test_a_subfolder_that_cannot_be_listed_refuses_a_send(tmp_path, places, clock, monkeypatch):
    older = tmp_path / "older"
    sub = older / "sub"
    write(sub / "run1_20260101T000000Z.jsonl")
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "older_records": [str(older)]}
    scandir = os.scandir

    def denied(path="."):
        if not isinstance(path, int) and Path(path) == sub:
            raise PermissionError(13, "Permission denied", str(path))
        return scandir(path)

    monkeypatch.setattr(os, "scandir", denied)
    site = FakeSite()
    with pytest.raises(runner.Refused, match="sub cannot be read: PermissionError"):
        send(write_manifest(tmp_path / "m"), site, places, clock, conf, max_order=1)
    assert not [c for c in site.calls if c[0] == "submit"]
    assert monitor.find(places, conf) == [monitor.Unread(str(older), f"{sub} cannot be read: PermissionError")]


def test_a_run_folder_of_the_app_that_cannot_be_listed_refuses_a_send(tmp_path, places, clock, monkeypatch):
    run = places.records / "euroqexa" / "x"
    write(run / "run_20260101T000000Z.jsonl")
    scandir = os.scandir

    def denied(path="."):
        if not isinstance(path, int) and Path(path) == run:
            raise PermissionError(13, "Permission denied", str(path))
        return scandir(path)

    monkeypatch.setattr(os, "scandir", denied)
    site = FakeSite()
    with pytest.raises(runner.Refused, match="x cannot be read: PermissionError"):
        send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1)
    assert not [c for c in site.calls if c[0] == "submit"]
    unread = monitor.Unread(str(places.records), f"{run} cannot be read: PermissionError")
    assert monitor.find(places, cfg()) == [unread]


def test_a_path_whose_stat_is_refused_gives_an_error_line(tmp_path, capsys, monkeypatch):
    places = places_in(tmp_path)
    places.config.write_text(CONFIG)
    p = write(tmp_path / "older" / "run1_20260101T000000Z.jsonl")
    refuse_stat(monkeypatch, p)
    clock = FakeClock()
    assert cli.main(["runs", str(p)], places=places, environ={}, clock=clock, sleep=clock.sleep, host="host-a") == 0
    assert capsys.readouterr().out.splitlines() == [f"{p}: {p} cannot be read: PermissionError"]


def test_a_record_whose_stat_is_refused_gives_an_error_line_and_refuses_a_send(tmp_path, places, clock, monkeypatch):
    rec = write(places.records / "euroqexa" / "x" / "run_20260101T000000Z.jsonl")
    refuse_stat(monkeypatch, rec)
    lines = [monitor.run_line(monitor.summary(p)) for p in monitor.find(places, cfg())]
    assert lines == [f"{rec}: {rec} cannot be read: PermissionError"]
    with pytest.raises(runner.Refused, match="cannot be read: PermissionError"):
        send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1)
