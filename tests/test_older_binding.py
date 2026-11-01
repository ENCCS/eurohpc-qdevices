"""A decision on an older record holds for the lines it was made on, while the order is as it was, for one site."""

import json

import pytest
from fakes import events, lines_of, records_of
from fakes.older import LOST, OLDER, OPEN, START, decide, decisions_file, listed, piastq_send, write

from qdevices import older, runner
from qdevices.ledger import Ledger
from qdevices.runner.preflight import SiteScan

FULL = [START, *LOST, {"event": "submitted", "order": 2, "name": "K2", "uid": "p-2"},
        {"event": "result", "order": 2, "name": "K2", "uid": "p-2", "shots": 200, "wall_seconds": 80.0}]
NO_SITE = [{"event": "start", "proposal": "TEST-AWARD", "utc": "2026-01-01T10:00:00+00:00"}, *OPEN]


def open_or_lost(rec, places) -> list:
    """The open or lost orders of a record, read with every decision of the app."""
    return Ledger(older.Decisions.load(places.records).merged(lines_of(rec))).open_or_lost


def test_the_decision_line_holds_the_job_id_and_the_lines_it_was_made_on(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "batch_20260101T100000Z.jsonl", OLDER)
    decide(rec, 1, places, clock, listed(places, piastq=[tmp_path / "older"]), "gone")
    line, = lines_of(decisions_file(places))
    assert (line["decided_id"], line["lines"], line["lines_sha256"]) == ("p-1", len(OLDER),
                                                                          older.binding(lines_of(rec))["lines_sha256"])


def test_a_none_on_a_shorter_copy_leaves_the_result_of_the_full_record(tmp_path, places, clock):
    part = write(tmp_path / "a" / "batch_20260101T100000Z.jsonl", [START, *LOST])     # copied while it ran
    full = write(tmp_path / "b" / "batch_20260101T100000Z.jsonl", FULL)
    conf = listed(places, piastq=[tmp_path / "a", tmp_path / "b"])
    assert "final with no job" in decide(part, 2, places, clock, conf)                 # lost in that copy
    decisions = older.Decisions.load(places.records)
    assert Ledger(decisions.merged(lines_of(part))).orders[2].final == "resolved_none"
    o = Ledger(decisions.merged(lines_of(full))).orders[2]
    assert (o.final, o.counted_seconds) == ("result", 80.0)                           # its result stands
    with pytest.raises(runner.Refused, match="is final: in a record of another runner --none"):
        decide(full, 2, places, clock, conf)
    assert piastq_send(tmp_path, places, clock, conf) == 0
    assert events(records_of(places)[0], "end")[-1]["used_seconds"] == 81.5        # 80 s, 0 s, the new job


def test_a_job_id_or_a_new_job_written_later_by_the_other_runner_opens_the_order_again(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "batch_20260101T100000Z.jsonl", OLDER)           # 1 open (p-1), 2 lost
    conf = listed(places, piastq=[tmp_path / "older"])
    decide(rec, 1, places, clock, conf, "gone")
    decide(rec, 2, places, clock, conf)
    assert open_or_lost(rec, places) == []
    with rec.open("a") as fh:                          # that runner goes on: an id for 2, and 1 sent once more
        for line in ({"event": "submitted", "order": 2, "name": "K2", "uid": "p-2"},
                     {"event": "submitting", "order": 1, "name": "K1"},
                     {"event": "submitted", "order": 1, "name": "K1", "uid": "p-9"}):
            fh.write(json.dumps(line) + "\n")
    assert open_or_lost(rec, places) == [(1, "open"), (2, "open")]
    with pytest.raises(runner.Refused, match="order 1 is open") as refused:
        piastq_send(tmp_path, places, clock, conf)
    assert "order 2 is open" in str(refused.value)


def test_another_record_with_the_same_first_line_and_a_shorter_copy_do_not_get_it(tmp_path, places, clock):
    rec = write(tmp_path / "a" / "batch_20260101T100000Z.jsonl", OLDER)
    other = write(tmp_path / "b" / "batch_20260101T100000Z.jsonl", [START, OPEN[0], {**OPEN[1], "uid": "p-7"},
                                                                    *OPEN[2:], *LOST])
    short = write(tmp_path / "c" / "batch_20260101T100000Z.jsonl", OLDER[:3])         # 1 open: copied earlier
    conf = listed(places, piastq=[tmp_path / "a", tmp_path / "b", tmp_path / "c"])
    decide(rec, 1, places, clock, conf, "gone")
    decide(rec, 2, places, clock, conf)
    assert older.start_digest(lines_of(other)) == older.start_digest(lines_of(rec))
    assert open_or_lost(rec, places) == []
    assert open_or_lost(other, places) == [(1, "open"), (2, "lost")]                   # not decided
    assert open_or_lost(short, places) == [(1, "open")]                               # stays blocked
    with pytest.raises(runner.Refused, match="open or lost"):
        piastq_send(tmp_path, places, clock, conf)


def test_a_send_reads_only_the_decisions_made_for_its_own_site(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "batch_20260101T100000Z.jsonl", NO_SITE)         # its site cannot be told
    assert "is final" in decide(rec, 1, places, clock, listed(places, vlq=[rec]), "gone")
    assert decisions_file(places, "vlq").is_file() and not decisions_file(places).exists()
    conf = listed(places, vlq=[rec], piastq=[rec])
    assert [s.ledger.open_or_lost for s in SiteScan.read(places, "vlq", conf["vlq"]).scans] == [[]]
    assert [s.ledger.open_or_lost for s in SiteScan.read(places, "piastq", conf["piastq"]).scans] == [[(1, "open")]]
    with pytest.raises(runner.Refused, match="open or lost"):
        piastq_send(tmp_path, places, clock, conf)
    with pytest.raises(runner.Refused, match="names no site, and the older_records of vlq and piastq hold it"):
        decide(rec, 1, places, clock, conf, "gone")


def test_a_record_in_the_records_folder_of_the_app_is_resolved_in_it(tmp_path, places, clock):
    rec = write(places.records / "piastq" / "x" / "run_20260101T100000Z.jsonl",        # no "app" in its lines
                [{"event": "start", "site": "piastq", "project": "TEST-PROJECT"},
                 {"event": "submitting", "order": 1, "name": "J1", "site": "piastq"}])
    conf = listed(places)
    with pytest.raises(runner.Refused, match="order 1 is lost"):
        piastq_send(tmp_path, places, clock, conf)
    assert "final with no job" in decide(rec, 1, places, clock, conf)
    assert lines_of(rec)[-1]["none"] is True and not decisions_file(places).exists()
    assert piastq_send(tmp_path, places, clock, conf) == 0
