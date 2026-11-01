"""`resolve` on a record of another runner: --none and --over-limit, what it refuses, and the site it is for."""

import pytest
from fakes import STATE, FakeSite, cfg, lines_of, records_of, send, write_manifest
from fakes.older import LOST, OPEN, RESULT, START, decide, decisions_file, listed, piastq_send, write

from qdevices import older, runner
from qdevices.ledger import Ledger
from qdevices.sites import SITES


def test_none_and_over_limit_on_a_record_of_another_runner(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", [START, *LOST, *RESULT])   # 2 lost, 3 at 500 s
    conf = listed(places, piastq=[tmp_path / "older"])
    before = rec.read_bytes()
    assert "final with no job" in decide(rec, 2, places, clock, conf)
    assert "counts at 100 s from now on" in decide(rec, 3, places, clock, conf, "over_limit")
    none, over = lines_of(decisions_file(places))
    assert (none["order"], none["none"]) == (2, True)
    assert (over["order"], over["over_limit"], over["measured_seconds"], over["counted_seconds"]) == (3, True, 500.0,
                                                                                                       100.0)
    lines = older.Decisions.load(places.records).merged(lines_of(rec))
    assert Ledger(lines).orders[2].final == "resolved_none" and Ledger(lines).open_or_lost == []
    assert Ledger(lines).used_seconds(50.0) == 100.0           # the result at the limit of the decision, the lost 0
    with pytest.raises(runner.Refused, match="resolved already"):
        decide(rec, 3, places, clock, conf, "over_limit")
    assert len(lines_of(decisions_file(places))) == 2 and rec.read_bytes() == before


def test_what_resolve_refuses_on_a_record_of_another_runner(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", [START, *OPEN, *LOST, *RESULT])
    conf = listed(places, piastq=[tmp_path / "older"])
    before = rec.read_bytes()
    for order, decision, job, why in ((2, None, "p-2", "does not collect it"),
                                      (1, "expired", None, "does not collect it"),
                                      (3, "gone", None, "is final: --gone"),
                                      (2, "gone", None, "is lost: --gone"),
                                      (9, "gone", None, "is not in the record: --gone"),
                                      (1, None, None, "is open: in a record of another runner --none")):
        with pytest.raises(runner.Refused, match=why):
            decide(rec, order, places, clock, conf, decision, job)
    assert not decisions_file(places).exists()
    decide(rec, 1, places, clock, conf, "gone")
    with pytest.raises(runner.Refused, match="is final: --gone"):
        decide(rec, 1, places, clock, conf, "gone")                      # a second --gone on the same order
    assert len(lines_of(decisions_file(places))) == 1 and rec.read_bytes() == before


def test_gone_is_refused_on_a_record_of_this_app(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 10),))
    assert send(m, FakeSite("piastq", states={"J-1": [STATE("Running")]}), places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    before = rec.read_bytes()
    assert Ledger(lines_of(rec)).orders[1].status == "open"
    with pytest.raises(runner.Refused, match=r"a record of this app: --gone .* --expired"):
        decide(rec, 1, places, clock, cfg(), "gone")
    assert rec.read_bytes() == before and not decisions_file(places).exists()


def test_the_record_must_be_held_by_the_older_records_of_one_site_that_reads_it(tmp_path, places, clock):
    folder = tmp_path / "older"
    rec = write(folder / "run1_20260101T100000Z.jsonl", [START, *OPEN])               # a record of Piast-Q
    unknown = write(folder / "run2_20260101T100000Z.jsonl", [{"event": "start", "proposal": "TEST-AWARD"}, *OPEN])
    no_start = write(folder / "run3_20260101T100000Z.jsonl", OPEN)
    for path, conf, why in (
            (rec, listed(places), "no older_records in qdevices.toml hold it. List it, or its folder,"),
            (rec, listed(places, euroqexa=[folder]), "for piastq, and only the older_records of euroqexa hold it"),
            (unknown, listed(places, euroqexa=[folder], vlq=[unknown]), "names no site, and the older_records of "
                                                                         "euroqexa and vlq hold it"),
            (no_start, listed(places, piastq=[folder]), "is not a start line")):
        with pytest.raises(runner.Refused, match=why):
            decide(path, 1, places, clock, conf, "gone")
    assert not any(decisions_file(places, site).exists() for site in SITES)
    decide(rec, 1, places, clock, listed(places, euroqexa=[folder], piastq=[rec]), "gone")   # read for piastq only
    assert len(lines_of(decisions_file(places))) == 1 and not decisions_file(places, "euroqexa").exists()


def test_resolve_takes_the_records_a_send_reads_through_a_link_too_and_no_other_file(tmp_path, places, clock):
    folder = tmp_path / "older"
    target = write(tmp_path / "archive" / "batch_20260101T100000Z.jsonl", [START, *OPEN])
    folder.mkdir()
    link = folder / target.name
    link.symlink_to(target)
    other = write(folder / "batch.json", [START, *LOST])                          # not a .jsonl file: never read
    conf = listed(places, piastq=[folder])
    with pytest.raises(runner.Refused, match=r"no older_records in qdevices.toml hold it"):
        decide(other, 2, places, clock, conf)
    with pytest.raises(runner.Refused, match="order 1 is open"):
        piastq_send(tmp_path, places, clock, conf)                   # a send reads the record through the link
    assert "is final" in decide(link, 1, places, clock, conf, "gone")
    assert lines_of(decisions_file(places))[0]["record"] == str(target.resolve())
    assert piastq_send(tmp_path, places, clock, conf) == 0 and lines_of(target) == [START, *OPEN]
