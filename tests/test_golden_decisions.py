"""Every `qdevices resolve` that writes: its answer and its one synced line under the lock, pinned whole."""

import json
from pathlib import Path

import pytest
from fakes import STATE, FakeSite, cfg, lines_of, records_of, send, write_manifest
from fakes.older import LOST, OLDER, RESULT, START, decide, decisions_file, listed, write
from fakes.piastq import EXPIRED, Broker, answer, run_broker

from qdevices import record, runner
from qdevices.resolve import EXPIRED_MINUTES, resolve

DAY = 86400.0
STEPS = [("created", {"job": 7}), ("uploaded", {"job": 7})]     # a VLQ job made, its files sent, no answer to submit


def synced(monkeypatch) -> list:
    """record._sync, noted: the list gets "sync" at each synced line."""
    seen = []
    monkeypatch.setattr(record, "_sync", lambda fd: seen.append("sync"))
    return seen


def watched(monkeypatch):
    """The list of synced(), and a take_lock that notes in it the lock and its release."""
    seen = synced(monkeypatch)

    def take(name):
        seen.append(("lock", name))
        return lambda: seen.append("release")
    return seen, take


def appending(path: Path, text: str):
    """A take_lock that appends `text` to `path` when it is called: what another process wrote before the lock."""
    def take(name):
        with path.open("a", encoding="utf-8") as fh:
            fh.write(text)
        return lambda: None
    return take


def last(path: Path) -> str:
    return path.read_text(encoding="utf-8").splitlines()[-1]


def lost(tmp_path, places, clock, site: str = "euroqexa") -> Path:
    """A record of the app whose order 1 is lost: the job request got no answer."""
    kw = {"seconds_left": 3600} if site == "vlq" else {}
    m = write_manifest(tmp_path / "m", site=site, jobs=(("J1", 10),))
    assert send(m, FakeSite(site, submits={1: ("noanswer",)}, **kw), places, clock, max_order=1) == 2
    return records_of(places)[0]


def resolved(monkeypatch, rec: Path, site: str, *args, **kw) -> str:
    """A resolve of a record of the app: its answer and the line it wrote, synced once under the lock."""
    seen, take = watched(monkeypatch)
    said = resolve(rec, *args, host="host-a", take_lock=take, **kw)
    assert seen == [("lock", site), "sync", "release"]
    return f"{said}\n{last(rec)}\n"


@pytest.mark.parametrize("site, job, name", [("vlq", "123", "decisions_job_vlq_number"),
                                             ("vlq", "J-5", "decisions_job_vlq_text"),
                                             ("euroqexa", "123", "decisions_job_euroqexa")])
def test_job_on_a_lost_order(tmp_path, places, clock, monkeypatch, golden, site, job, name):
    rec = lost(tmp_path, places, clock, site)
    golden(name, resolved(monkeypatch, rec, site, 1, job, places=places, clock=clock))


def test_none_on_a_lost_order(tmp_path, places, clock, monkeypatch, golden):
    rec = lost(tmp_path, places, clock)
    golden("decisions_none_lost", resolved(monkeypatch, rec, "euroqexa", 1, None, places=places, clock=clock))


def test_none_on_an_open_vlq_order_whose_last_stop_is_submit_unknown(tmp_path, places, clock, monkeypatch, golden):
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("J1", 10),))
    site = FakeSite("vlq", seconds_left=3600, submits={1: ("steps", ("noanswer",), STEPS)})
    assert send(m, site, places, clock, max_order=1) == 2                     # unknown, with the job 7
    rec = records_of(places)[0]
    later = FakeSite("vlq", seconds_left=3600, states={7: [STATE("Configuring", configuring=True)]})
    assert send(m, later, places, clock, resume=rec) == 1                     # submit_unknown
    golden("decisions_none_submit_unknown", resolved(monkeypatch, rec, "vlq", 1, None, places=places, clock=clock))


def test_none_on_an_order_still_new(tmp_path, places, clock, monkeypatch, golden):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, FakeSite(states={"J-1": [STATE("New")]}), places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    clock.t += 4 * DAY
    assert send(m, FakeSite(states={"J-1": [STATE("New")]}), places, clock, resume=rec) == 2    # New on the day
    golden("decisions_none_still_new", resolved(monkeypatch, rec, "euroqexa", 1, None, places=places, clock=clock))


def test_over_limit_in_a_record_of_the_app(tmp_path, places, clock, monkeypatch, golden):
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "budget_seconds": 600.0, "job_seconds_limit": 300.0}
    site = FakeSite()
    site.result = lambda job_id: {"counts": {"1": 10}, "seconds": 5000.0}
    assert send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), site, places, clock, conf, max_order=1) == 2
    text = resolved(monkeypatch, records_of(places)[0], "euroqexa", 1, None, places=places, clock=clock,
                    decision="over_limit", cfg=conf)
    golden("decisions_over_limit_app", text)


def test_expired_in_a_record_of_the_app(tmp_path, places, clock, monkeypatch, golden):
    broker = Broker(results=[answer(200, json=EXPIRED)])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    clock.t += 60
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    clock.t += EXPIRED_MINUTES * 60
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    text = resolved(monkeypatch, rec, "piastq", 1, None, places=places, clock=clock, decision="expired", cfg=cfg())
    golden("decisions_expired_app", text)


def test_unreadable_in_a_record_of_the_app(tmp_path, places, clock, monkeypatch, golden):
    broker = Broker(results=[answer(200, json={"result": [["a"]]})])       # a shot that is not bits
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    clock.t += EXPIRED_MINUTES * 60
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    text = resolved(monkeypatch, rec, "piastq", 1, None, places=places, clock=clock, decision="unreadable",
                    cfg=cfg())
    golden("decisions_unreadable_app", text)


@pytest.mark.parametrize("name, lines, order, decision", [("decisions_none_older", OLDER, 2, None),
                                                          ("decisions_gone_older", OLDER, 1, "gone"),
                                                          ("decisions_over_limit_older", [START, *LOST, *RESULT], 3,
                                                           "over_limit")])
def test_each_decision_on_a_record_of_another_runner(tmp_path, places, clock, monkeypatch, golden, name, lines,
                                                      order, decision):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", lines)
    conf = listed(places, piastq=[tmp_path / "older"])
    before = rec.read_bytes()
    seen, take = watched(monkeypatch)
    said = decide(rec, order, places, clock, conf, decision, take_lock=take)
    assert seen == [("lock", "piastq"), "sync", "release"] and rec.read_bytes() == before
    golden(name, f"{said}\n{last(decisions_file(places))}\n")


def test_a_line_appended_before_the_lock_to_a_record_of_the_app_decides(tmp_path, places, clock, monkeypatch, golden):
    rec = lost(tmp_path, places, clock)                       # lost at the first read; open under the lock
    line = json.dumps({"event": "submitted", "order": 1, "name": "J1", "id": "J-9"}) + "\n"
    before, seen = rec.read_bytes(), synced(monkeypatch)
    with pytest.raises(runner.Refused) as refused:
        resolve(rec, 1, None, places=places, clock=clock, host="host-a", take_lock=appending(rec, line))
    assert rec.read_bytes() == before + line.encode() and seen == []
    golden("decisions_app_changed_under_lock", f"{refused.value}\n")


def test_a_decision_appended_before_the_lock_decides(tmp_path, places, clock, monkeypatch, golden):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    conf = listed(places, piastq=[tmp_path / "older"])
    decide(rec, 2, places, clock, conf)                       # the line another resolve writes, taken away again
    target = decisions_file(places)
    line = target.read_text(encoding="utf-8")
    target.unlink()
    seen = synced(monkeypatch)
    with pytest.raises(runner.Refused) as refused:            # lost at the first read; decided under the lock
        decide(rec, 2, places, clock, conf, take_lock=appending(target, line))
    assert target.read_text(encoding="utf-8") == line and seen == []
    golden("decisions_older_decided_under_lock", f"{refused.value}\n")


def test_a_decision_holds_the_lines_read_under_the_lock(tmp_path, places, clock, golden):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    conf = listed(places, piastq=[tmp_path / "older"])
    line = json.dumps({"event": "stop", "order": 1, "kind": "http_error", "http_status": 502}) + "\n"
    said = decide(rec, 1, places, clock, conf, "gone", take_lock=appending(rec, line))     # the other runner goes on
    decision = last(decisions_file(places))
    assert json.loads(decision)["lines"] == len(lines_of(rec)) == len(OLDER) + 1
    golden("decisions_older_grew_under_lock", f"{said}\n{decision}\n")


@pytest.mark.parametrize("order, job, decision", [(1, None, None), (1, "J-9", None), (9, None, None),
                                                  (1, None, "over_limit"), (2, None, "over_limit"),
                                                  (1, None, "expired"), (1, None, "unreadable"), (1, None, "gone")])
def test_a_refused_resolve_of_a_record_with_a_cut_last_line_writes_and_syncs_nothing(tmp_path, places, clock,
                                                                                     monkeypatch, order, job,
                                                                                     decision):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10)))
    assert send(m, FakeSite(submits={2: ("noanswer",)}), places, clock, max_order=2) == 2     # 1 final, 2 lost
    rec = records_of(places)[0]
    with rec.open("a", encoding="utf-8") as fh:
        fh.write('{"event": "status", "order": 2, "na')         # a crash inside a write: no newline at the end
    before = rec.read_bytes()
    seen, take = watched(monkeypatch)
    with pytest.raises(runner.Refused):
        resolve(rec, order, job, places=places, clock=clock, host="host-a", take_lock=take, decision=decision,
                cfg=cfg())
    assert rec.read_bytes() == before and "sync" not in seen
