"""A result the broker no longer gives: a stop of the kind result_expired, then `resolve --expired`."""

import pytest
from fakes import STATE, FakeSite, cfg, events, lines_of, records_of, send, write_manifest
from fakes.piastq import EXPIRED, Broker, answer, piastq_manifest, run_broker

from qdevices import runner
from qdevices.ledger import Ledger
from qdevices.resolve import EXPIRED_MINUTES, resolve


def expire(rec, places, clock, order=1):
    return resolve(rec, order, None, places=places, clock=clock, host="host-a", decision="expired", cfg=cfg())


@pytest.mark.parametrize("code", [200, 404, 500])
def test_the_answer_that_the_job_may_be_expired_stops_with_the_order_open(tmp_path, places, clock, code):
    broker = Broker(results=[answer(code, json=EXPIRED)])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    stop = events(rec, "stop")[-1]
    assert stop["kind"] == "result_expired" and stop["http_status"] == (None if code == 200 else code)
    assert "Unknown job. May be expired." in stop["body"] and "--expired" in stop["reason"]
    assert Ledger(lines_of(rec)).orders[1].status == "open"
    assert broker.count("POST", "/tasks") == 1
    assert broker.count("GET", "/results") == 1             # not a missed poll, whatever the HTTP status


def test_a_status_read_with_that_answer_stops_the_same_way_and_is_not_a_failed_job(tmp_path, places, clock):
    broker = Broker(states=[answer(200, json=EXPIRED)])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    stop = events(rec, "stop")[-1]
    assert stop["kind"] == "result_expired" and stop["step"] == "status" and not events(rec, "failed")
    assert Ledger(lines_of(rec)).orders[1].status == "open" and broker.count("GET", "/results") == 0


def test_resolve_expired_needs_two_calls_ten_minutes_apart_then_the_order_is_final(tmp_path, places, clock):
    broker = Broker(results=[answer(200, json=EXPIRED)])
    run_broker(tmp_path, places, clock, broker)
    rec = records_of(places)[0]
    with pytest.raises(runner.Refused, match="one call only"):
        expire(rec, places, clock)
    clock.t += 60
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1           # collect only: the same answer
    with pytest.raises(runner.Refused, match=f"less than {EXPIRED_MINUTES} minutes"):
        expire(rec, places, clock)
    clock.t += EXPIRED_MINUTES * 60
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert "never sent again" in expire(rec, places, clock)
    line = events(rec, "resolved")[-1]
    assert line["expired"] is True and line["counted_seconds"] == 100.0
    lines = lines_of(rec)
    assert Ledger(lines).orders[1].final == "resolved_expired"
    assert Ledger(lines).used_seconds(50.0) == 100.0         # the seconds of the decision, not a later limit
    with pytest.raises(runner.Refused, match="not open"):
        expire(rec, places, clock)
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 0           # final: nothing more is asked
    assert broker.count("POST", "/tasks") == 1
    other = piastq_manifest(tmp_path / "other")
    assert send(other, FakeSite("piastq"), places, clock, max_order=1) == 0       # a new run is allowed again


def test_resolve_expired_is_refused_for_any_other_order(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10)))
    send(m, FakeSite(submits={2: ("noanswer",)}), places, clock, max_order=2)    # 1 final, 2 lost
    rec = records_of(places)[0]
    for order, status in ((1, "final"), (2, "lost"), (9, "not in the record")):
        with pytest.raises(runner.Refused, match=f"is {status}: --expired"):
            expire(rec, places, clock, order)
    n = write_manifest(tmp_path / "n", site="piastq", jobs=(("J1", 10),))
    assert send(n, FakeSite("piastq", states={"J-1": [STATE("Running")]}), places, clock, max_order=1) == 2
    timed_out = next(p for p in records_of(places) if "piastq" in p.parts)
    with pytest.raises(runner.Refused, match="last stop is not result_expired"):
        expire(timed_out, places, clock)
    assert Ledger(lines_of(timed_out)).orders[1].status == "open"
