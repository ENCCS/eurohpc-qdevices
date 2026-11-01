"""The full text of every refusal of `qdevices resolve`, in a record of the app and of another runner."""

from functools import partial
from pathlib import Path

import pytest
from fakes import STATE, FakeSite, cfg, places_in, records_of, send, write_manifest
from fakes.older import LOST, OLDER, OPEN, RESULT, START, decide, decisions_file, listed, write
from fakes.piastq import EXPIRED, Broker, answer, run_broker

from qdevices import lock, record, runner
from qdevices.resolve import resolve

DAY = 86400.0
ONE = (("J1", 10),)
STEPS = [("created", {"job": 7}), ("uploaded", {"job": 7})]     # a VLQ job made, its files sent, no answer to submit
NO_SITE = [{"event": "start", "proposal": "TEST-AWARD", "utc": "2026-01-01T10:00:00+00:00"}, *OPEN]


def files_below(root: Path) -> dict:
    """The bytes of every file below `root`, but those of the lock folders."""
    return {p: p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and "state" not in p.relative_to(root).parts}


def refusals(root: Path, monkeypatch):
    """A resolve that must be refused: it gives the text, after it checks that nothing was written or synced."""
    syncs = []
    monkeypatch.setattr(record, "_sync", lambda fd: syncs.append(fd))

    def refused(rec, order, job=None, decision=None, **kw) -> str:
        before = files_below(root)
        syncs.clear()
        with pytest.raises(runner.Refused) as caught:
            resolve(rec, order, job, host="host-a", decision=decision, **kw)
        assert files_below(root) == before and syncs == []
        return str(caught.value)
    return refused


def table(rows) -> str:
    return "".join(f"{case}:\n  {text}\n" for case, text in rows)


def test_refusals_of_final_lost_and_unsent_orders(tmp_path, clock, monkeypatch, golden):
    refused = refusals(tmp_path, monkeypatch)
    a = places_in(tmp_path / "a")
    assert send(write_manifest(tmp_path / "a" / "m"), FakeSite(submits={2: ("noanswer",)}), a, clock, max_order=2) == 2
    at = partial(refused, records_of(a)[0], places=a, clock=clock, cfg=cfg())        # 1 final, 2 lost, 3 not sent
    rows = [("--none on a final order", at(1)), ("--job on a final order", at(1, "J-9")),
            ("--none on an order not in the record", at(9)),
            ("--over-limit on a result within the limit", at(1, decision="over_limit")),
            ("--over-limit on a lost order", at(2, decision="over_limit")),
            ("--over-limit on an order not in the record", at(9, decision="over_limit")),
            ("--expired on a final order", at(1, decision="expired")),
            ("--expired on a lost order", at(2, decision="expired")),
            ("--expired on an order not in the record", at(9, decision="expired"))]
    f = places_in(tmp_path / "f")
    assert send(write_manifest(tmp_path / "f" / "m", jobs=ONE), FakeSite(max_shots=5), f, clock, max_order=1) == 2
    at = partial(refused, records_of(f)[0], places=f, clock=clock, cfg=cfg())         # a rule stopped it: unsent
    rows += [("--none on an order a rule kept from being sent", at(1)),
             ("--over-limit on that order", at(1, decision="over_limit"))]
    j, conf = places_in(tmp_path / "j"), cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "budget_seconds": 600.0, "job_seconds_limit": 300.0}
    site = FakeSite()
    site.result = lambda job_id: {"counts": {"1": 10}, "seconds": 5000.0}
    assert send(write_manifest(tmp_path / "j" / "m", jobs=ONE), site, j, clock, conf, max_order=1) == 2   # job_time
    resolve(records_of(j)[0], 1, None, places=j, clock=clock, host="host-a", decision="over_limit", cfg=conf)
    rows.append(("--over-limit on an order resolved over the limit",
                 refused(records_of(j)[0], 1, decision="over_limit", places=j, clock=clock, cfg=conf)))
    golden("decisions_refused_app_closed", table(rows))


def test_refusals_of_open_orders(tmp_path, clock, monkeypatch, golden):
    refused = refusals(tmp_path, monkeypatch)
    b = places_in(tmp_path / "b")
    m = write_manifest(tmp_path / "b" / "m", jobs=ONE)
    assert send(m, FakeSite(states={"J-1": [STATE()]}), b, clock, max_order=1) == 2      # the wait timed out
    at = partial(refused, records_of(b)[0], places=b, clock=clock, cfg=cfg())
    rows = [("--none on an open order the site showed as RUNNING", at(1)), ("--job on it", at(1, "J-9")),
            ("--expired on it", at(1, decision="expired")), ("--over-limit on it", at(1, decision="over_limit"))]
    c = places_in(tmp_path / "c")
    m = write_manifest(tmp_path / "c" / "m", site="vlq", jobs=ONE)
    assert send(m, FakeSite("vlq", seconds_left=3600, submits={1: ("steps", ("noanswer",), STEPS)}), c, clock,
                max_order=1) == 2                                                         # unknown, with the job 7
    at = partial(refused, records_of(c)[0], places=c, clock=clock, cfg=cfg())
    rows.append(("--none on an open order with no status line", at(1)))
    configuring = FakeSite("vlq", seconds_left=3600, states={7: [STATE("Configuring", configuring=True)]})
    assert send(m, configuring, c, clock, resume=records_of(c)[0]) == 1                  # submit_unknown
    rows.append(("--job on an open VLQ order whose last stop is submit_unknown", at(1, "7")))
    d = places_in(tmp_path / "d")
    m = write_manifest(tmp_path / "d" / "m", jobs=ONE)
    assert send(m, FakeSite(states={"J-1": [STATE("New")]}), d, clock, max_order=1) == 2
    at = partial(refused, records_of(d)[0], places=d, clock=clock, cfg=cfg())
    rows.append(("--none on an order New for less than 3 days", at(1)))
    clock.t += 4 * DAY
    rows.append(("--none on an order New whose last read is 4 days old", at(1)))
    assert send(m, FakeSite(states={"J-1": [STATE("New")]}), d, clock, resume=records_of(d)[0]) == 2
    rows.append(("--job on an order still New", at(1, "J-1")))
    assert send(m, FakeSite(states={"J-1": [STATE("Queued")]}), d, clock, resume=records_of(d)[0]) == 2
    rows.append(("--none on an order the site showed as Queued", at(1)))
    e, broker = places_in(tmp_path / "e"), Broker(results=[answer(200, json=EXPIRED)])
    assert run_broker(tmp_path / "e", e, clock, broker) == 1                              # result_expired
    at = partial(refused, records_of(e)[0], places=e, clock=clock, cfg=cfg())
    rows.append(("--expired after one call got result_expired", at(1, decision="expired")))
    clock.t += 60
    assert run_broker(tmp_path / "e", e, clock, broker, resume=records_of(e)[0]) == 1
    rows.append(("--expired after two calls a minute apart", at(1, decision="expired")))
    golden("decisions_refused_app_open", table(rows))


def test_refusals_of_a_record_of_the_app_before_its_orders_are_read(tmp_path, clock, monkeypatch, golden):
    refused = refusals(tmp_path, monkeypatch)
    r = places_in(tmp_path / "r")
    assert send(write_manifest(tmp_path / "r" / "m", jobs=ONE), FakeSite(submits={1: ("noanswer",)}), r, clock,
                max_order=1) == 2                                                         # order 1 lost
    at = partial(refused, places=r, clock=clock, cfg=cfg())
    rows = [("--gone on a record of the app", at(records_of(r)[0], 1, decision="gone"))]
    held = lock.Locks(r.state, host="host-a").take("euroqexa")
    rows.append(("--none on a lost order while the lock of its site is held", at(records_of(r)[0], 1)))
    held()
    no_site = write(r.records / "euroqexa" / "x" / "run_20260101T100000Z.jsonl",
                    [{"event": "start", "app": "qdevices"}, {"event": "submitting", "order": 1, "name": "J1"}])
    (tmp_path / "folder").mkdir()
    rows += [("a record of the app that names no site", at(no_site, 1)),
             ("a record that does not exist", at(tmp_path / "absent.jsonl", 1)),
             ("a folder in place of a record", at(tmp_path / "folder", 1))]
    golden("decisions_refused_app_record", table(rows))


def test_refusals_of_the_orders_of_a_record_of_another_runner(tmp_path, places, clock, monkeypatch, golden):
    refused = refusals(tmp_path, monkeypatch)
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", [START, *OPEN, *LOST, *RESULT])
    conf = listed(places, piastq=[tmp_path / "older"])                 # 1 open, 2 lost, 3 a result of 500 s
    within = {**conf, "piastq": {**conf["piastq"], "job_seconds_limit": 600.0}}
    at = partial(refused, rec, places=places, clock=clock, cfg=conf)
    rows = [("--job", at(2, "p-2")), ("--expired", at(1, decision="expired")),
            ("--gone on a final order", at(3, decision="gone")), ("--gone on a lost order", at(2, decision="gone")),
            ("--gone on an order not in the record", at(9, decision="gone")),
            ("--none on an open order", at(1)), ("--none on a final order", at(3)),
            ("--none on an order not in the record", at(9)),
            ("--over-limit on an open order", at(1, decision="over_limit")),
            ("--over-limit on a lost order", at(2, decision="over_limit")),
            ("--over-limit on an order not in the record", at(9, decision="over_limit")),
            ("--over-limit on a result within the limit", at(3, decision="over_limit", cfg=within))]
    held = lock.Locks(places.state, host="host-a").take("piastq")
    rows.append(("--none on a lost order while the lock of the site is held", at(2)))
    held()
    decide(rec, 1, places, clock, conf, "gone")
    decide(rec, 3, places, clock, conf, "over_limit")
    rows += [("--gone on an order decided gone", at(1, decision="gone")), ("--none on that order", at(1)),
             ("--over-limit on an order resolved over the limit", at(3, decision="over_limit"))]
    golden("decisions_refused_older_orders", table(rows))


def test_refusals_of_a_record_of_another_runner_for_its_site(tmp_path, places, clock, monkeypatch, golden):
    refused = refusals(tmp_path, monkeypatch)
    folder = tmp_path / "older"
    rec = write(folder / "run1_20260101T100000Z.jsonl", [START, *OPEN])                  # a record of Piast-Q
    unknown = write(tmp_path / "no-site" / "run2_20260101T100000Z.jsonl", NO_SITE)
    no_start = write(tmp_path / "no-start" / "run3_20260101T100000Z.jsonl", OPEN)
    gone = partial(refused, order=1, decision="gone", places=places, clock=clock)
    rows = [("a record listed in no older_records", gone(rec, cfg=listed(places))),
            ("a record listed only for another site", gone(rec, cfg=listed(places, euroqexa=[folder]))),
            ("a record with no site listed for two sites",
             gone(unknown, cfg=listed(places, euroqexa=[unknown], vlq=[unknown.parent]))),
            ("a record with no site listed in no older_records", gone(unknown, cfg=listed(places))),
            ("a record whose first line is not a start line", gone(no_start, cfg=listed(places, piastq=[no_start])))]
    other = places_in(tmp_path / "other")
    (other.records / "piastq" / "older_decisions.jsonl").mkdir(parents=True)
    rows.append(("a decisions path that is a folder",
                 gone(rec, places=other, cfg=listed(places, piastq=[folder]))))
    golden("decisions_refused_older_sites", table(rows))


def test_a_record_removed_between_the_two_reads(tmp_path, places, clock):
    """Of another runner and of the app: refused. Fault 5 of the plan, fixed: it was a RecordError for the app."""
    def removing(path: Path):
        def take(name):
            path.unlink()
            return lambda: None
        return take

    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    conf = listed(places, piastq=[tmp_path / "older"])
    with pytest.raises(runner.Refused) as refused:
        decide(rec, 2, places, clock, conf, take_lock=removing(rec))
    assert str(refused.value) == f"no record at {rec}" and not decisions_file(places).exists()
    m = write_manifest(tmp_path / "m", jobs=ONE)
    assert send(m, FakeSite(submits={1: ("noanswer",)}), places, clock, max_order=1) == 2      # order 1 lost
    own = records_of(places)[0]
    with pytest.raises(runner.Refused, match="no record at"):
        resolve(own, 1, None, places=places, clock=clock, host="host-a", take_lock=removing(own))
