"""Records as `runs`, `resolve` and `send` read and write them, in cases that no other test covers."""

import json
import os
from pathlib import Path

import pytest
from fakes import CONFIG, FakeSite, cfg, events, lines_of, records_of, send, write_manifest
from fakes.older import OPEN, decide, listed, main, write
from fakes.piastq import Broker, piastq_manifest

from qdevices import config
from qdevices.resolve import resolve

NO_SITE = [{"event": "start", "proposal": "TEST-AWARD", "utc": "2026-01-01T10:00:00+00:00"}, *OPEN]
LONG = b"{" * ((1 << 20) + 1)            # a first line longer than the 1 MiB a reader of an older folder takes


def run(places, clock, capsys, *args) -> tuple[int, str]:
    """One command through cli.main: its exit code, and the command with what it printed and its exit code."""
    args = [str(a) for a in args]
    capsys.readouterr()
    code = main(places, clock, *args)
    out, err = capsys.readouterr()
    return code, f"$ qdevices {' '.join(args)}\n{out}" + (f"stderr:\n{err}" if err else "") + f"exit {code}\n"


def test_an_unlistable_subfolder_is_named_before_a_first_line_that_cannot_be_read(tmp_path, places, clock, capsys,
                                                                                    monkeypatch, golden):
    older = tmp_path / "older"
    sub = older / "sub"
    write(sub / "run1_20260101T000000Z.jsonl", OPEN)
    (older / "batch.jsonl").write_bytes(LONG)                  # not named run*.jsonl: its first line is read
    listed(places, euroqexa=[older])
    code, alone = run(places, clock, capsys, "runs")           # the long first line alone
    assert code == 0 and "batch.jsonl cannot be read" in alone
    scandir = os.scandir

    def denied(path="."):
        if not isinstance(path, int) and Path(path) == sub:
            raise PermissionError(13, "Permission denied", str(path))
        return scandir(path)

    monkeypatch.setattr(os, "scandir", denied)
    code, both = run(places, clock, capsys, "runs")
    assert code == 0 and f"{sub} cannot be read: PermissionError" in both and "batch.jsonl" not in both
    golden("units_records_unlistable_and_long_first_line", alone + both)


def test_runs_of_a_record_with_no_site_and_a_vlq_decision_shows_unknown(tmp_path, places, clock, capsys, golden):
    rec = write(tmp_path / "older" / "batch_20260101T100000Z.jsonl", NO_SITE)
    decide(rec, 1, places, clock, listed(places, vlq=[rec]), "gone")              # read for vlq only
    runs, usage = (run(places, clock, capsys, command) for command in ("runs", "usage"))
    assert runs[0] == usage[0] == 0
    assert any(line.startswith(f"unknown  TEST-AWARD  older  {rec}: ") for line in runs[1].splitlines())
    golden("units_records_no_site_vlq_decision", runs[1] + usage[1])


def test_resolve_none_needs_no_config_and_a_decision_with_a_limit_reads_it(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, FakeSite(submits={1: ("noanswer",)}), places, clock, max_order=1) == 2        # order 1 lost
    rec = records_of(places)[0]
    places.config.mkdir()                                      # a qdevices.toml that cannot be read
    with pytest.raises(config.ConfigError):
        config.load(places.config)
    assert resolve(rec, 1, None, places=places, clock=clock, host="host-a") == "order 1 is final with no job"
    assert lines_of(rec)[-1]["event"] == "resolved" and lines_of(rec)[-1]["none"] is True
    before = rec.read_bytes()
    with pytest.raises(config.ConfigError):
        resolve(rec, 1, None, places=places, clock=clock, host="host-a", decision="over_limit")
    assert rec.read_bytes() == before


def test_a_site_whose_result_is_none_ends_with_exit_code_3(tmp_path, places, clock, golden):
    site = FakeSite()
    site.result = lambda job_id: None
    assert send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), site, places, clock, max_order=1) == 3
    rec = records_of(places)[0]
    assert events(rec, "stop")[-1]["kind"] == "error" and not events(rec, "result")
    golden("record_units_result_none", rec.read_text(encoding="utf-8"))


def windowed(tmp_path, places, clock, window: str) -> tuple[int, Broker, list]:
    """A send of one Piast-Q job to the fake broker with this window: the exit code, the broker, what a hook saw."""
    table = f'[piastq]\nwindow = {json.dumps([window])}\nwindow_zone = "Europe/Warsaw"\n'
    conf = cfg(CONFIG.replace("[piastq]\n", table))
    broker, seen = Broker(), []
    user = {"before_job": lambda job, state: seen.append(state["in_window"]) or {"passed": True}}
    code = send(piastq_manifest(tmp_path / "m"), broker.site(), places, clock, conf, max_order=1, user_rules=user)
    return code, broker, seen


def test_outside_the_piastq_window_a_rule_stops_the_call_before_the_job(tmp_path, places, clock, golden):
    code, broker, seen = windowed(tmp_path, places, clock, "Mon 09:00-12:00")    # 13:00 in Warsaw
    rec = records_of(places)[0]
    stop = events(rec, "stop")[-1]
    assert code == 2 and (stop["kind"], stop["rule"]) == ("rule", "window") and seen == [False]
    assert broker.count("POST", "/tasks") == 0 and not events(rec, "submitting")
    golden("record_units_window_outside", rec.read_text(encoding="utf-8"))


def test_inside_the_piastq_window_the_job_is_sent(tmp_path, places, clock):
    code, broker, seen = windowed(tmp_path, places, clock, "Mon 12:00-14:00")
    assert code == 0 and broker.count("POST", "/tasks") == 1 and seen == [True]
    assert [e["in_window"] for e in events(records_of(places)[0], "rule") if e["rule"] == "window"] == [True]
