"""`resolve --gone` on a record of another runner: one line in a file of the app; the record is never written."""

import shutil
from pathlib import Path

import pytest
from fakes import events, lines_of, records_of
from fakes.older import OLDER, decide, decisions_file, line_of, listed, main, piastq_send, write

from qdevices import cli, older, record, runner
from qdevices.ledger import Ledger


def runs(places, clock, capsys) -> list[str]:
    """The lines of `qdevices runs`, which ends with exit code 0."""
    capsys.readouterr()
    assert main(places, clock, "runs") == 0
    return capsys.readouterr().out.splitlines()


def test_gone_writes_one_line_in_the_decisions_file_and_never_the_record(tmp_path, places, clock, capsys):
    rec = write(tmp_path / "older" / "batch_20260101T100000Z.jsonl", OLDER)
    conf = listed(places, piastq=[tmp_path / "older"])
    before = rec.read_bytes()
    assert "open or lost: order 1 open, order 2 lost" in line_of(runs(places, clock, capsys), rec)
    with pytest.raises(runner.Refused, match="open or lost"):
        piastq_send(tmp_path, places, clock, conf)
    assert "is final" in decide(rec, 1, places, clock, conf, "gone")
    line, = lines_of(decisions_file(places))
    assert {k: line[k] for k in ("event", "app", "site", "order", "name", "by_host", "gone", "counted_seconds")} == {
        "event": "resolved", "app": "qdevices", "site": "piastq", "order": 1, "name": "K1", "by_host": "host-a",
        "gone": True, "counted_seconds": 100.0}
    assert line["start_sha256"] == older.start_digest(lines_of(rec)) and line["record"] == str(rec.resolve())
    assert rec.read_bytes() == before
    with pytest.raises(runner.Refused, match="order 2 is lost") as refused:
        piastq_send(tmp_path, places, clock, conf)
    assert "order 1 is" not in str(refused.value)                                     # no longer refused for it
    assert "final with no job" in decide(rec, 2, places, clock, conf)                 # --none on the lost order
    assert len(lines_of(decisions_file(places))) == 2 and rec.read_bytes() == before
    assert piastq_send(tmp_path, places, clock, conf) == 0                            # nothing blocks a start now
    assert events(records_of(places)[0], "end")[-1]["used_seconds"] == 101.5          # 100 s for the gone order
    lines = older.Decisions.load(places.records).merged(lines_of(rec))
    assert Ledger(lines).used_seconds(30.0) == 100.0          # the limit on the day of the decision, not a later one
    assert Ledger(lines_of(rec)).used_seconds(30.0) == 60.0   # without the decisions: open and lost, at the limit
    assert "open or lost" not in line_of(runs(places, clock, capsys), rec)
    assert rec.read_bytes() == before


def test_a_copy_of_the_record_in_another_folder_gets_the_same_decisions(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "batch_20260101T100000Z.jsonl", OLDER)
    copy = tmp_path / "copy" / rec.name
    copy.parent.mkdir()
    shutil.copy(rec, copy)
    conf = listed(places, piastq=[tmp_path / "older", tmp_path / "copy"])
    decide(rec, 1, places, clock, conf, "gone")
    decide(rec, 2, places, clock, conf)
    assert Ledger(older.Decisions.load(places.records).merged(lines_of(copy))).open_or_lost == []
    with pytest.raises(runner.Refused, match="is final: --gone"):
        decide(copy, 1, places, clock, conf, "gone")                     # decided already, through the record
    assert piastq_send(tmp_path, places, clock, conf) == 0                # both are read, and both are decided
    assert events(records_of(places)[0], "end")[-1]["used_seconds"] == 201.5      # two copies count twice
    assert len(lines_of(decisions_file(places))) == 2


def test_a_decisions_file_that_cannot_be_read_refuses_a_send_and_gives_a_line_in_runs_and_usage(
        tmp_path, places, clock, capsys, monkeypatch):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    conf = listed(places, piastq=[tmp_path / "older"])
    decide(rec, 1, places, clock, conf, "gone")
    decide(rec, 2, places, clock, conf)
    target = decisions_file(places)
    read_bytes = Path.read_bytes

    def denied(path):
        if path == target:
            raise PermissionError(13, "Permission denied")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(runner.Refused, match=r"older_decisions.jsonl cannot be read: PermissionError"):
        piastq_send(tmp_path, places, clock, conf)
    lines = runs(places, clock, capsys)
    assert lines[0] == f"{target}: {target} cannot be read: PermissionError"
    assert "open or lost: order 1 open, order 2 lost" in line_of(lines, rec)       # read without the decisions
    assert main(places, clock, "usage") == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"{target}: {target} cannot be read: PermissionError; {cli.NO_DECISIONS}"
    assert any(line.split()[:3] == ["piastq", "TEST-AWARD", "1"] for line in lines)   # the record is in the totals
    assert not any("they are not in the totals" in line for line in lines)


def test_the_decision_is_one_synced_line_written_under_the_lock_of_the_site(tmp_path, places, clock, monkeypatch):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    conf = listed(places, piastq=[tmp_path / "older"])
    seen = []
    monkeypatch.setattr(record, "_sync", lambda fd: seen.append("sync"))

    def take(name):
        seen.append(("lock", name))
        return lambda: seen.append("release")

    decide(rec, 1, places, clock, conf, "gone", take_lock=take)
    assert seen == [("lock", "piastq"), "sync", "release"]


def test_resolve_gone_and_jobs_from_the_command_line(tmp_path, places, clock, capsys):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    listed(places, piastq=[tmp_path / "older"])
    before = rec.read_bytes()
    assert main(places, clock, "resolve", str(rec), "1", "--gone") == 0
    assert main(places, clock, "resolve", str(rec), "1", "--gone") == 1               # refused: final already
    assert main(places, clock, "resolve", str(rec), "2", "--job", "p-2") == 1         # the app does not collect it
    assert main(places, clock, "resolve", str(rec), "2", "--gone", "--none") == 1     # one decision at a time
    assert main(places, clock, "resolve", str(rec), "2", "--none") == 0
    assert [line.get("gone") or line.get("none") for line in lines_of(decisions_file(places))] == [True, True]
    capsys.readouterr()
    assert main(places, clock, "jobs", str(rec)) == 0
    rows = {row.split()[0]: row for row in capsys.readouterr().out.splitlines()[1:] if row.split()[0].isdigit()}
    assert "resolved_gone" in rows["1"] and "resolved_none" in rows["2"] and rec.read_bytes() == before
