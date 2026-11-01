"""The send loop with a fake site: the order of the requests, the lines on disk before them, and resume."""

import pytest
from fakes import STATE, FakeSite, events, lines_of, records_of, send, write_manifest

from qdevices import runner
from qdevices.ledger import Ledger


def test_a_run_sends_each_order_once_in_order(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    site = FakeSite(record=lambda: records_of(places)[0])
    assert send(m, site, places, clock, max_order=3) == 0
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 1), ("submit", 2), ("submit", 3)]
    rec = records_of(places)[0]
    assert [e["order"] for e in events(rec, "result")] == [1, 2, 3]
    assert events(rec, "end")[0]["left"] == []


def test_the_submitting_line_is_on_disk_before_the_request(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    site = FakeSite(record=lambda: records_of(places)[0])
    send(m, site, places, clock, max_order=2)
    assert [(line["event"], line["order"]) for line in site.seen_on_disk] == [("submitting", 1), ("submitting", 2)]


def test_each_step_line_is_on_disk_before_the_next_request(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    steps = [("created", {"job": 7}), ("uploaded", {"job": 7})]
    site = FakeSite(record=lambda: records_of(places)[0], submits={1: ("steps", ("id", 7), steps)})
    send(m, site, places, clock, max_order=1)
    assert [(line["event"], line.get("step")) for line in site.seen_on_disk] == \
        [("submitting", None), ("step", "created"), ("step", "uploaded")]


def test_max_order_stops_the_loop(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    site = FakeSite()
    assert send(m, site, places, clock, max_order=1) == 0
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 1)]
    assert events(records_of(places)[0], "end")[0]["left"] == [2, 3]


def test_a_live_call_needs_a_stage(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    site = FakeSite()
    with pytest.raises(runner.Refused):
        send(m, site, places, clock)
    assert site.calls == []


def test_resume_goes_on_and_never_sends_an_order_again(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    rec = records_of(places)[0]
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, max_order=3) == 0
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 2), ("submit", 3)]


def test_a_start_beside_a_record_with_jobs_needs_new_run(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    clock.t += 5
    with pytest.raises(runner.Refused, match="--new-run"):
        send(m, FakeSite(), places, clock, max_order=1)
    site = FakeSite()
    assert send(m, site, places, clock, max_order=1, new_run=True) == 0
    assert ("submit", 1) in site.calls and len(records_of(places)) == 2

def test_resume_collects_an_open_id_and_does_not_send_it_again(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    running = STATE()
    site = FakeSite(states={"J-1": [running]})
    assert send(m, site, places, clock, max_order=1) == 2               # the wait time-out
    rec = records_of(places)[0]
    assert events(rec, "stop")[-1]["kind"] == "timeout"
    assert Ledger(lines_of(rec)).orders[1].status == "open"
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec) == 0                # collect only
    assert site.calls == [("status", "J-1"), ("result", "J-1")]


def test_collect_only_makes_no_request_that_can_make_a_job(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    site = FakeSite()
    assert send(m, site, places, clock, resume=records_of(places)[0]) == 0
    assert not [c for c in site.calls if c[0] in ("submit", "prepare", "read")]


def test_extra_manifest_keys_go_to_the_start_line(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", experiment={"angle": 0.5})
    send(m, FakeSite(), places, clock, max_order=1)
    assert events(records_of(places)[0], "start")[0]["extra"] == {"experiment": {"angle": 0.5}}
