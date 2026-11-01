"""A read in the wait with no answer, a 5xx or busy is a missed poll, asked again until wait_seconds.

One POST for each job, and no transport retry: only the reads of the state and of the result are asked again.
"""

from fakes import STATE, FakeSite, cfg, events, lines_of, records_of, send, write_manifest
from fakes.piastq import BUSY, COUNTS, Broker, answer, run_broker

from qdevices import runner
from qdevices.ledger import Ledger
from qdevices.sites import piastq
from qdevices.sites.base import NoAnswer, SiteError


def test_a_busy_result_read_is_asked_again_at_the_next_poll(tmp_path, places, clock):
    broker = Broker(results=[answer(422, text=BUSY), answer(200, json=COUNTS)])
    assert run_broker(tmp_path, places, clock, broker) == 0
    rec = records_of(places)[0]
    assert len(events(rec, "result")) == 1 and events(rec, "result")[0]["counts"] == {"00": 6, "11": 4}
    assert broker.count("GET", "/results") == 2 and broker.count("POST", "/tasks") == 1
    missed = [e for e in events(rec, "status") if e.get("missed")]
    assert [(e["missed"], e["step"]) for e in missed] == [("busy", "result")]


def test_a_status_read_with_no_answer_is_asked_again_and_a_line_is_written_when_the_kind_changes(
        tmp_path, places, clock):
    lost = NoAnswer("no answer to GET status: ConnectError", step="status")
    busy = SiteError("HTTP 503 to GET status", status=503, step="status")
    site = FakeSite(states={"J-1": [lost, lost, busy, busy, STATE("COMPLETED", final=True, ok=True)]})
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, site, places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    assert len(events(rec, "result")) == 1
    lines = [(e.get("missed"), e.get("state")) for e in events(rec, "status")]
    assert lines == [("no answer", None), ("HTTP 503", None), (None, "COMPLETED")]
    assert [c[0] for c in site.calls].count("status") == 5 and [c[0] for c in site.calls].count("submit") == 1


def test_a_result_that_answers_500_at_every_poll_stops_at_wait_seconds_with_the_order_open(tmp_path, places, clock):
    broker = Broker(results=[answer(500, text="")])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    stop = events(rec, "stop")[-1]
    assert stop["kind"] == "result_error" and stop["http_status"] == 500 and stop["missed_polls"] == 6
    assert "same day" in stop["reason"]                     # Piast-Q: collect an open order the same day
    assert clock.t == 60.0                                   # wait_seconds of the test config
    assert Ledger(lines_of(rec)).orders[1].status == "open"
    assert broker.count("POST", "/tasks") == 1 and broker.count("GET", "/results") == 7
    assert len([e for e in events(rec, "status") if e.get("missed")]) == 1
    later = Broker()
    assert run_broker(tmp_path, places, clock, later, resume=rec) == 0                 # a resume collects it
    assert later.count("POST", "/tasks") == 0 and len(events(rec, "result")) == 1


def test_any_other_failed_read_ends_the_wait_at_once(tmp_path, places, clock):
    site = FakeSite(states={"J-1": [SiteError("HTTP 403 to GET status", status=403, step="status")]})
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, site, places, clock, max_order=1) == 1
    stop = events(records_of(places)[0], "stop")[-1]
    assert stop["kind"] == "status_error" and stop["missed_polls"] == 0 and stop["http_status"] == 403
    assert [c[0] for c in site.calls].count("status") == 1 and clock.t == 0.0


def test_a_long_network_loss_still_ends_the_call_at_wait_seconds(tmp_path, places, clock):
    site = FakeSite(states={"J-1": [NoAnswer("no answer to GET status: ConnectError", step="status")]})
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, site, places, clock, max_order=1) == 1
    rec = records_of(places)[0]
    stop = events(rec, "stop")[-1]
    assert stop["kind"] == "status_error" and "after 12 missed polls" in stop["reason"]
    assert Ledger(lines_of(rec)).orders[1].status == "open" and clock.t == 60.0
    assert [c[0] for c in site.calls].count("submit") == 1


def test_a_stop_that_leaves_a_piastq_order_open_says_to_collect_it_the_same_day(tmp_path, places, clock):
    broker = Broker(states=[answer(200, json={"status": "Running"})])
    assert run_broker(tmp_path, places, clock, broker) == 2                 # the wait time-out
    assert "Collect it the same day" in events(records_of(places)[0], "stop")[-1]["reason"]

    def hit():
        raise KeyboardInterrupt()

    said = []
    site = FakeSite(states={"J-1": [hit]})
    site.collect_note = piastq.PiastQ.collect_note
    m = write_manifest(tmp_path / "n", jobs=(("J1", 10),))
    assert runner.send(m, site, cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="host-a",
                       say=said.append, max_order=1) == 130
    assert said[-1] == piastq.PiastQ.collect_note
