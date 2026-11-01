"""The older records below a listed folder, by name (run*.jsonl) or start line, and the "expired" line."""

import json
import re
from pathlib import Path

import pytest
from fakes import cfg, events, records_of
from fakes.older import START, piastq_send, write

from qdevices import finder, monitor, older, record, runner
from qdevices.ledger import Ledger

SRC = Path(__file__).resolve().parent.parent / "src" / "qdevices"
EVENT_CALL = re.compile(r'\.(?:write|final)\(\s*"(\w+)"')    # the literal event name of a call that writes a line
EXPIRED = [START, {"event": "submitting", "order": 1, "name": "K1"},
           {"event": "submitted", "order": 1, "name": "K1", "uid": "p-1"},
           {"event": "expired", "order": 1, "uid": "p-1", "raw": "Unknown job. May be expired."}]


def with_older(*folders) -> dict:
    conf = cfg()
    conf["piastq"] = {**conf["piastq"], "older_records": [str(f) for f in folders]}
    return conf


def test_below_a_folder_a_record_is_told_by_its_name_or_by_its_start_line(tmp_path):
    folder = tmp_path / "older"
    taken = [write(folder / "run1_20260101T000000Z.jsonl", EXPIRED[1:]),        # a run name, whatever it holds
             write(folder / "batch_20260101T000000Z.jsonl", EXPIRED),
             write(folder / "sub" / "other.jsonl", [START])]
    write(folder / "notes.jsonl", EXPIRED[1:])                                  # the first line is not a start line
    write(folder / "start.json", [START])                                       # not a .jsonl file
    write(folder / "list.jsonl", [[START]])                                     # a list, not an object
    (folder / "cut.jsonl").write_text(json.dumps(START)[:20])                   # a cut first line
    (folder / "empty.jsonl").write_text("")
    assert finder.OlderRecords(folder).files() == sorted(taken)
    assert finder.OlderRecords(folder / "notes.jsonl").files() == [folder / "notes.jsonl"]   # a place that is a file


def test_a_first_line_that_cannot_be_read_refuses_a_send_and_gives_an_error_line(tmp_path, places, clock,
                                                                                 monkeypatch):
    folder = tmp_path / "older"
    bad = write(folder / "batch_20260101T000000Z.jsonl", EXPIRED)
    path_open = Path.open

    def denied(self, *args, **kwargs):
        if self == bad:
            raise PermissionError(13, "Permission denied", str(self))
        return path_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied)
    conf = with_older(folder)
    with pytest.raises(runner.Refused, match=r"batch_20260101T000000Z.jsonl cannot be read: PermissionError"):
        piastq_send(tmp_path, places, clock, conf)
    assert monitor.find(places, conf) == [monitor.Unread(str(folder), f"{bad} cannot be read: PermissionError")]


def test_a_first_line_longer_than_the_cap_makes_the_folder_unreadable(tmp_path):
    folder = tmp_path / "older"
    long = write(folder / "batch_20260101T000000Z.jsonl", [{**START, "pad": "x" * finder.FIRST_LINE}])
    with pytest.raises(record.RecordError, match="its first line is longer than 1 MiB"):
        finder.OlderRecords(folder).files()              # not passed over: whether it is a record cannot be told
    assert finder.OlderRecords(long).files() == [long]  # by its own path it is taken, whatever its first line
    write(long, [{**START, "pad": "x" * (finder.FIRST_LINE - 200)}])
    assert finder.OlderRecords(folder).files() == [long]


def test_an_expired_line_after_a_result_leaves_the_result():
    result = {"event": "result", "order": 1, "name": "K1", "uid": "p-1", "shots": 200, "wall_seconds": 61.0}
    for lines in ([*EXPIRED[:3], result, EXPIRED[3]], [*EXPIRED, result]):
        o = Ledger(lines).orders[1]
        assert (o.final, Ledger(lines).used_seconds(100.0)) == ("result", 61.0)


def test_the_decisions_file_is_never_read_as_a_record(places):
    target = write(places.records / "piastq" / older.DECISIONS,
                   [{"event": "resolved", "order": 1, "gone": True, "start_sha256": "0" * 64}])
    app = write(places.records / "piastq" / "m" / "run_20260101T000000Z.jsonl",
                [{"event": "start", "app": "qdevices", "site": "piastq"}])
    assert finder.AppRecords(places.records / "piastq").files() == [app]
    assert finder.OlderRecords(places.records).files() == [app]
    assert monitor.find(places, with_older(places.records)) == [app] and target.is_file()


def test_an_expired_line_of_an_older_runner_is_final_and_counts_at_the_job_time_limit(tmp_path, places, clock):
    o = Ledger(EXPIRED).orders[1]
    assert (o.final, o.status, o.counted) == ("expired", "final", None)
    assert Ledger(EXPIRED).open_or_lost == [] and Ledger(EXPIRED[:3]).open_or_lost == [(1, "open")]
    assert Ledger(EXPIRED).used_seconds(100.0) == 100.0
    write(tmp_path / "older" / "batch_20260101T000000Z.jsonl", EXPIRED)
    assert piastq_send(tmp_path, places, clock, with_older(tmp_path / "older")) == 0   # it no longer blocks a start
    assert events(records_of(places)[0], "end")[-1]["used_seconds"] == 101.5   # 100 s for it, 1.5 s for the new job


def test_no_event_this_app_writes_is_named_expired():
    """Each event name given as a literal to .write( or to .final( (a call that writes a last line) is listed."""
    assert EVENT_CALL.findall('call.final("result", order=1)\nrec.write(\n    "stop", kind=k)') == ["result", "stop"]
    listed = record.__doc__.split("Event names written by this app:")[1].split("\n\n")[0]
    names = set(" ".join(listed.split()).strip(" .").split(", "))
    written = set()
    for path in SRC.rglob("*.py"):
        written |= set(EVENT_CALL.findall(path.read_text(encoding="utf-8")))
    assert "resolved" in written and written <= names and "expired" not in names
