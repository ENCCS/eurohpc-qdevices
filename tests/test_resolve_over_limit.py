"""`resolve --over-limit`: a result above job_seconds_limit counts at the limit, after a decision in the record."""

import shlex

import pytest
from fakes import CONFIG, STATE, FakeClock, FakeSite, cfg, events, lines_of, places_in, records_of, send, write_manifest

from qdevices import cli, monitor, record, runner
from qdevices.ledger import Ledger
from qdevices.resolve import resolve

WAITED = 5000.0                       # a synthetic wait at the site, in the seconds of one result


def limits() -> dict:
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "budget_seconds": 600.0, "job_seconds_limit": 300.0, "award_hours": 10}
    return conf


def waited(name="euroqexa", **kw):
    site = FakeSite(name, **kw)
    site.result = lambda job_id: {"counts": {"1": 10}, "seconds": WAITED}
    return site


def over(rec, places, clock, conf, order=1, **kw):
    return resolve(rec, order, None, places=places, clock=clock, host="host-a", decision="over_limit", cfg=conf, **kw)


def test_a_result_resolved_over_the_limit_counts_at_the_limit_in_the_budget(tmp_path, places, clock):
    conf = limits()
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, waited(), places, clock, conf, max_order=1) == 2               # the rule job_time stops
    rec = records_of(places)[0]
    stop = events(rec, "stop")[-1]
    assert stop["rule"] == "job_time" and f"qdevices resolve {shlex.quote(str(rec))} 1 --over-limit" in stop["reason"]
    other = write_manifest(tmp_path / "other", jobs=(("J1", 10),))
    site = FakeSite()
    assert send(other, site, places, clock, conf, max_order=1) == 2               # the rule budget stops
    assert not [c for c in site.calls if c[0] == "submit"]
    assert "300 s from now on" in over(rec, places, clock, conf)
    line = events(rec, "resolved")[-1]
    assert line["over_limit"] is True and line["measured_seconds"] == WAITED and line["counted_seconds"] == 300.0
    assert events(rec, "result")[-1]["seconds"] == WAITED                           # the measured seconds stay
    assert Ledger(lines_of(rec)).used_seconds(50.0) == 300.0     # the seconds of the decision, not a later limit
    clock.t += 5
    site = FakeSite()
    assert send(other, site, places, clock, conf, max_order=1) == 0
    assert ("submit", 1) in site.calls


def test_runs_and_usage_show_the_measured_and_the_counted_seconds(tmp_path, places, clock):
    conf = limits()
    send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), waited(), places, clock, conf, max_order=1)
    rec = records_of(places)[0]
    over(rec, places, clock, conf)
    s = monitor.summary(rec)
    assert s.seconds == WAITED and s.counted == 300.0 and s.decided == 1
    assert "5000.0 s measured; 300.0 s counted" in monitor.run_line(s)
    award = next(line for line in monitor.usage([s], conf) if line.startswith("euroqexa: award 10 h"))
    assert "5,000.0 s measured" in award and "(13.89 %)" in award and "300.0 s counted (0.83 %)" in award


def test_resolve_over_limit_is_refused_within_the_limit_open_lost_and_resolved(tmp_path, places, clock):
    conf = limits()
    send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), waited(), places, clock, conf, max_order=1)
    rec = records_of(places)[0]
    over(rec, places, clock, conf)
    with pytest.raises(runner.Refused, match="resolved already"):
        over(rec, places, clock, conf)
    m = write_manifest(tmp_path / "p", site="piastq", jobs=(("J1", 10), ("J2", 10)))
    send(m, FakeSite("piastq", submits={2: ("noanswer",)}), places, clock, max_order=2)   # 1 within, 2 lost
    within = next(p for p in records_of(places) if "piastq" in p.parts)
    for order, why in ((1, "within job_seconds_limit"), (2, "is lost"), (9, "is not in the record")):
        with pytest.raises(runner.Refused, match=why):
            over(within, places, clock, cfg(), order)
    v = write_manifest(tmp_path / "v", site="vlq", jobs=(("J1", 10),))
    assert send(v, FakeSite("vlq", seconds_left=3600, states={"J-1": [STATE()]}), places, clock, max_order=1) == 2
    timed_out = next(p for p in records_of(places) if "vlq" in p.parts)
    with pytest.raises(runner.Refused, match="is open"):
        over(timed_out, places, clock, cfg())


def test_the_decision_is_one_synced_line_written_under_the_site_lock(tmp_path, places, clock, monkeypatch):
    conf = limits()
    send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), waited(), places, clock, conf, max_order=1)
    rec = records_of(places)[0]
    before, seen = len(lines_of(rec)), []
    monkeypatch.setattr(record, "_sync", lambda fd: seen.append("sync"))

    def take(name):
        seen.append(("lock", name))
        return lambda: seen.append("release")

    over(rec, places, clock, conf, take_lock=take)
    assert seen == [("lock", "euroqexa"), "sync", "release"]
    assert len(lines_of(rec)) == before + 1


def test_a_piastq_result_collected_by_a_later_call_counts_its_wall_seconds_until_resolved(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 10),))
    assert send(m, FakeSite("piastq", seconds_kind="wall", states={"J-1": [STATE()]}), places, clock,
                max_order=1) == 2                                                  # the wait time-out
    rec = records_of(places)[0]
    clock.t += 3600
    site = FakeSite("piastq", seconds_kind="wall")
    site.result = lambda job_id: {"counts": {"1": 10}, "seconds": None}
    assert send(m, site, places, clock, resume=rec) == 2                       # job_time: from submission to now
    assert events(rec, "result")[-1]["seconds"] == 3660.0 and events(rec, "result")[-1]["recovered"] is True
    assert Ledger(lines_of(rec)).used_seconds(100.0) == 3660.0                 # before the decision: the wall seconds
    over(rec, places, clock, cfg())
    assert Ledger(lines_of(rec)).used_seconds(100.0) == 100.0


def test_resolve_over_limit_from_the_command_line(tmp_path):
    places, clock = places_in(tmp_path), FakeClock()
    places.config.write_text(CONFIG)
    send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), waited(), places, clock, max_order=1)
    rec = records_of(places)[0]

    def main(*args):
        return cli.main(["resolve", str(rec), "1", *args], places=places, environ={}, clock=clock,
                        sleep=clock.sleep, host="host-a")

    assert main("--over-limit") == 0
    assert events(rec, "resolved")[-1]["counted_seconds"] == 100.0                  # job_seconds_limit of CONFIG
    assert main("--over-limit") == 1                                                 # refused: resolved already
    assert main("--over-limit", "--expired") == 1                                    # one decision at a time
