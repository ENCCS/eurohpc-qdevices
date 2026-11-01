"""`runs` and `usage`: an older record folder or a PATH that cannot be read gives an error line."""

import os
from pathlib import Path

from fakes import CONFIG, FakeClock, FakeSite, cfg, places_in, send, write_manifest

from qdevices import cli, monitor
from qdevices.sites import SITES

SITE_NAMES = tuple(f"{name} " for name in SITES)


def lines_of(places, conf, extra=()) -> tuple[list[str], list[str]]:
    summaries = [monitor.summary(p) for p in monitor.find(places, conf, extra)]
    return [monitor.run_line(s) for s in summaries], monitor.usage(summaries, conf)


def test_an_older_record_folder_that_does_not_exist_gives_an_error_line(tmp_path, places):
    absent = tmp_path / "absent"
    conf = cfg()
    conf["vlq"] = {**conf["vlq"], "older_records": [str(absent)]}
    runs, usage = lines_of(places, conf)
    line = f"{absent}: {absent} cannot be read: FileNotFoundError"
    assert runs == [line]
    assert line in usage and "The records and folders above cannot be read: they are not in the totals." in usage


def test_a_path_that_does_not_exist_gives_an_error_line_beside_the_records(tmp_path, places, clock):
    send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1)
    runs, _ = lines_of(places, cfg(), [tmp_path / "absent.jsonl"])
    assert len(runs) == 2 and runs[0].startswith("euroqexa  TEST-PROJECT  m  ")
    assert runs[1] == f"{tmp_path / 'absent.jsonl'}: {tmp_path / 'absent.jsonl'} cannot be read: FileNotFoundError"


def test_a_folder_that_cannot_be_listed_gives_an_error_line(tmp_path, places, monkeypatch):
    locked = tmp_path / "locked"
    locked.mkdir()
    scandir = os.scandir

    def denied(path="."):
        if not isinstance(path, int) and Path(path) == locked:
            raise PermissionError(13, "Permission denied")
        return scandir(path)

    monkeypatch.setattr(os, "scandir", denied)
    runs, _ = lines_of(places, cfg(), [locked])
    assert runs == [f"{locked}: {locked} cannot be read: PermissionError"]


def test_a_relative_path_gives_its_error_line_with_the_absolute_path(tmp_path, places, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runs, _ = lines_of(places, cfg(), [Path("vlq x")])
    assert runs == [f"{Path('vlq x').absolute()}: vlq x cannot be read: FileNotFoundError"]
    for line in runs:
        assert not line.startswith(SITE_NAMES) and "open or lost" not in line


def test_runs_and_usage_print_the_error_line(tmp_path, capsys):
    places = places_in(tmp_path)
    places.config.write_text(CONFIG)
    clock = FakeClock()
    for command in ("runs", "usage"):
        code = cli.main([command, str(tmp_path / "absent")], places=places, environ={}, clock=clock,
                        sleep=clock.sleep, host="host-a")
        assert code == 0
        out = capsys.readouterr().out
        assert f"{tmp_path / 'absent'}: {tmp_path / 'absent'} cannot be read: FileNotFoundError" in out
        assert "no records found" not in out
    assert cli.main(["runs"], places=places, environ={}, clock=clock, sleep=clock.sleep, host="host-a") == 0
    assert "no records found" in capsys.readouterr().out
