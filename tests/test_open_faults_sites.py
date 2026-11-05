"""Sites and resolve: one program a file, a result that is never readable, HEAppE states, the request guard.

And a time below zero: in the stamps of Euro-Q-Exa, at a Piast-Q result collected late, and at a VLQ init job.
"""

import base64
import json
import pickle
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from fakes import CONFIG, QASM, STATE, FakeClock, FakeSite, cfg, eqe, events, lines_of, records_of, send, write_manifest
from fakes.older import OPEN, START, decide, listed, write
from fakes.piastq import Broker, answer, piastq_manifest, run_broker
from fakes.vlq import creates, make_vlq, submits
from test_units_vlq import make

from qdevices import cli, monitor, record, runner
from qdevices.ledger import Ledger
from qdevices.resolve import EXPIRED_MINUTES, resolve
from qdevices.resolve.resolution import Resolution
from qdevices.sites import local_time
from qdevices.sites.base import Channel, SiteError, UnsafeRequest, http_client
from qdevices.sites.euroqexa import EuroQExa
from qdevices.sites.vlq.wire import HeappeState

ROOT = Path(__file__).resolve().parent.parent
ONE_PROGRAM = "a file to send holds one job"
UNREADABLE = answer(200, json={"result": [["a"]]})       # a shot that is not bits: the result cannot be read
KEYS = local_time.STAMPS


def job(text: bytes) -> dict:
    return {"text": text, "shots": 10, "options": {}}


def unreadable(rec, places, clock, order=1, conf=None, **kw) -> str:
    return resolve(rec, order, None, places=places, clock=clock, host="host-a", decision="unreadable",
                   cfg=conf or cfg(), **kw)


# --------------------------------------------------------------------- one OpenQASM program a file

def test_a_euroqexa_file_of_more_than_one_openqasm_program_is_refused():
    two = QASM + b"// J2\n" + QASM
    assert EuroQExa.validate(job(two), None) == [f"the file holds 2 OpenQASM programs: {ONE_PROGRAM}"]
    assert EuroQExa.validate(job(b"// OPENQASM 2.0; in a comment opens no program\n" + QASM), None) == []
    assert EuroQExa.validate(job(QASM), None) == []


def test_the_dry_run_refuses_the_joined_qasm_output_of_a_folder_of_several_jobs(tmp_path, places, capsys):
    folder = ROOT / "examples" / "euroqexa-three-jobs"
    jobs = json.loads((folder / "manifest.json").read_text())["jobs"]
    joined = "".join(f"// {j['name']}\n" + (folder / j["file"]).read_text() for j in jobs)    # as --qasm prints it
    m = write_manifest(tmp_path / "m", jobs=(("ALL", 100),), text=joined.encode())
    places.config.write_text(CONFIG)
    clock = FakeClock()
    code = cli.main(["dry-run", str(m)], places=places, environ={}, clock=clock, sleep=clock.sleep, host="host-a")
    out = capsys.readouterr().out
    assert code == 1 and f"FAILED: order 1 (ALL): the file holds 3 OpenQASM programs: {ONE_PROGRAM}" in out
    assert out.rstrip().endswith("Dry run FAILED. Nothing was sent.")


def test_a_send_of_a_file_of_two_programs_stops_at_its_check_and_sends_nothing(tmp_path, places, clock):
    seen = []
    code, lines = eqe.send(eqe.manifest(tmp_path / "m", QASM + QASM), eqe.Portal(5, [(0, 1)], seen), places, clock,
                           max_order=1)
    assert code == 1 and lines[-1]["kind"] == "check" and eqe.posts(seen) == []
    assert lines[-1]["problems"] == [f"order 1 (J1): the file holds 2 OpenQASM programs: {ONE_PROGRAM}"]


# --------------------------------------------------------------------- a result that is never readable

def test_resolve_unreadable_needs_two_calls_ten_minutes_apart_then_the_order_is_final(tmp_path, places, clock):
    broker = Broker(results=[UNREADABLE])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    assert events(rec, "stop")[-1]["kind"] == "result_error"
    with pytest.raises(runner.Refused, match="one call only"):
        unreadable(rec, places, clock)
    clock.t += 60
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1           # collect only: the same answer
    with pytest.raises(runner.Refused, match=f"less than {EXPIRED_MINUTES} minutes"):
        unreadable(rec, places, clock)
    clock.t += EXPIRED_MINUTES * 60
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert "its result cannot be read; it is never sent again, and it counts at 100 s" in unreadable(rec, places, clock)
    line = events(rec, "resolved")[-1]
    assert (line["order"], line["unreadable"], line["counted_seconds"]) == (1, True, 100.0)
    lines = lines_of(rec)
    assert Ledger(lines).orders[1].final == "resolved_unreadable" and Ledger(lines).open_or_lost == []
    assert Ledger(lines).used_seconds(50.0) == 100.0         # the seconds of the decision, not a later limit
    with pytest.raises(runner.Refused, match="is final: --unreadable"):
        unreadable(rec, places, clock)
    reads = broker.count("GET", "/results")
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 0           # final: nothing more is asked
    assert broker.count("GET", "/results") == reads and broker.count("POST", "/tasks") == 1
    assert send(piastq_manifest(tmp_path / "other"), FakeSite("piastq"), places, clock, max_order=1) == 0


def test_vlq_result_files_that_never_give_the_device_seconds_are_resolved_unreadable(tmp_path, places, clock):
    def no_seconds(request: httpx.Request):
        if b"/job.pkl" in request.content:                                         # no remote_hw_runtime at all
            return httpx.Response(200, json=base64.b64encode(pickle.dumps({})).decode())
        return None

    fake, m, site = make(tmp_path, places, clock, {"DownloadFileFromCluster": no_seconds})
    assert send(m, site, places, clock, max_order=1) == 1
    rec = records_of(places)[0]
    for _ in range(2):
        clock.t += EXPIRED_MINUTES * 60
        assert send(m, site, places, clock, resume=rec) == 1
    assert [stop["kind"] for stop in events(rec, "stop")] == ["result_error"] * 3
    assert "counts at 100 s" in unreadable(rec, places, clock)
    summary = monitor.summary(rec)
    assert (summary.decided, summary.counted, summary.open) == (1, 100.0, [])
    assert len(creates(fake)) == 2 and len(submits(fake)) == 2           # the init job and the metered job, once


def test_resolve_unreadable_is_refused_for_any_other_order(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10)))
    send(m, FakeSite(submits={2: ("noanswer",)}), places, clock, max_order=2)    # 1 final, 2 lost
    rec = records_of(places)[0]
    for order, status in ((1, "final"), (2, "lost"), (9, "not in the record")):
        with pytest.raises(runner.Refused, match=f"is {status}: --unreadable takes only an open order whose last "
                                                 "stop is result_error"):
            unreadable(rec, places, clock, order)
    n = write_manifest(tmp_path / "n", site="piastq", jobs=(("J1", 10),))
    assert send(n, FakeSite("piastq", states={"J-1": [STATE("Running")]}), places, clock, max_order=1) == 2
    timed_out = next(p for p in records_of(places) if "piastq" in p.parts)
    with pytest.raises(runner.Refused, match="last stop is not result_error"):
        unreadable(timed_out, places, clock)
    assert Ledger(lines_of(timed_out)).orders[1].status == "open"


def test_resolve_unreadable_is_refused_on_a_record_of_another_runner(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", [START, *OPEN])
    conf = listed(places, piastq=[tmp_path / "older"])
    before = rec.read_bytes()
    with pytest.raises(runner.Refused, match="does not collect it, so --job, --expired and --unreadable are not"):
        decide(rec, 1, places, clock, conf, "unreadable")
    assert rec.read_bytes() == before


def test_the_unreadable_decision_is_one_synced_line_under_the_site_lock(tmp_path, places, clock, monkeypatch):
    broker = Broker(results=[UNREADABLE])
    run_broker(tmp_path, places, clock, broker)
    rec = records_of(places)[0]
    clock.t += EXPIRED_MINUTES * 60
    run_broker(tmp_path, places, clock, broker, resume=rec)
    before, seen = len(lines_of(rec)), []
    monkeypatch.setattr(record, "_sync", lambda fd: seen.append("sync"))

    def take(name):
        seen.append(("lock", name))
        return lambda: seen.append("release")

    unreadable(rec, places, clock, take_lock=take)
    assert seen == [("lock", "piastq"), "sync", "release"] and len(lines_of(rec)) == before + 1


def test_resolve_unreadable_from_the_command_line(tmp_path, places, clock):
    places.config.write_text(CONFIG)
    broker = Broker(results=[UNREADABLE])
    run_broker(tmp_path, places, clock, broker)
    rec = records_of(places)[0]
    clock.t += EXPIRED_MINUTES * 60
    run_broker(tmp_path, places, clock, broker, resume=rec)

    def main(*args):
        return cli.main(["resolve", str(rec), "1", *args], places=places, environ={}, clock=clock,
                        sleep=clock.sleep, host="host-a")

    assert main("--unreadable", "--expired") == 1                                   # one decision at a time
    assert main("--unreadable") == 0
    assert events(rec, "resolved")[-1]["counted_seconds"] == 100.0                  # job_seconds_limit of CONFIG
    assert main("--unreadable") == 1                                                 # refused: final now


# --------------------------------------------------------------------- the reads of resolve

def test_resolve_reads_the_record_once_to_find_the_site_then_again_under_the_lock(tmp_path, places, clock,
                                                                                    monkeypatch):
    broker = Broker(results=[UNREADABLE])
    run_broker(tmp_path, places, clock, broker)
    rec = records_of(places)[0]
    clock.t += EXPIRED_MINUTES * 60
    run_broker(tmp_path, places, clock, broker, resume=rec)
    seen, read = [], Resolution.read
    monkeypatch.setattr(Resolution, "read", staticmethod(lambda path: seen.append("read") or read(path)))

    def take(name):
        seen.append("lock")
        return lambda: seen.append("release")

    unreadable(rec, places, clock, take_lock=take)
    assert seen == ["read", "lock", "read", "release"]


# --------------------------------------------------------------------- HEAppE states

@pytest.mark.parametrize("code", [True, False, 1.0, 16.0, "1", None], ids=repr)
def test_a_heappe_state_that_is_not_a_whole_number_is_no_known_state(code):
    state = HeappeState.of(code)
    assert state.name == f"unknown({code!r})" and not (state.final or state.ok or state.configuring)


def test_the_heappe_states_of_whole_numbers_keep_their_names():
    assert (HeappeState.of(1).name, HeappeState.of(1).configuring) == ("Configuring", True)
    assert (HeappeState.of(16).name, HeappeState.of(16).ok, HeappeState.of(512).name) == ("Finished", True,
                                                                                         "unknown(512)")


def test_a_heappe_answer_whose_state_is_true_has_no_state(tmp_path):
    _places, _clock, _fake, _m, site = make_vlq(tmp_path, states={7: [True]})
    with pytest.raises(SiteError, match="the answer has no state"):
        site.status(7)


def test_a_vlq_job_made_and_never_submitted_whose_state_reads_true_stays_open(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path, states={7: [True]})
    made = FakeSite("vlq", seconds_left=3600, submits={1: ("steps", ("interrupt",), [("created", {"job": 7})])})
    assert send(m, made, places, clock, max_order=1) == 130             # interrupted after CreateJob, before uploads
    rec = records_of(places)[0]
    assert send(m, site, places, clock, resume=rec) == 1
    stop = events(rec, "stop")[-1]
    assert (stop["kind"], stop["error"]) == ("status_error", "the answer has no state")
    assert events(rec, "not_submitted") == [] and Ledger(lines_of(rec)).orders[1].status == "open"
    assert creates(fake) == [] and submits(fake) == []                  # a resume makes and sends no job


# --------------------------------------------------------------------- Euro-Q-Exa stamps

@pytest.mark.parametrize("stamps, submitted_utc", [
    (("2027-10-20 14:00:00", "2027-10-20 14:00:30", "2027-10-20 14:00:10"), None),
    (("2027-10-20 14:00:00", "2027-10-20 14:00:30", "2027-10-20 14:00:10"), "2027-10-20T12:00:00+00:00"),
    (("2027-10-31 02:40:00", "2027-10-31 02:50:00", "2027-10-31 02:10:00"), None),
], ids=["no-time-of-the-app", "time-of-the-app", "the-repeated-october-hour"])
def test_euroqexa_stamps_that_give_a_time_below_zero_give_no_seconds(stamps, submitted_utc):
    out = local_time.site_times(dict(zip(KEYS, stamps, strict=True)), submitted_utc)
    assert out["seconds"] is None and out["zone_check"] is False


def test_a_euroqexa_result_whose_stamps_run_backwards_holds_no_seconds_below_zero(tmp_path, places, clock):
    backwards = {**eqe.STAMPS, "timestamp_completed": "2026-01-05 12:59:59"}     # before it was scheduled
    code, lines = eqe.send(eqe.manifest(tmp_path / "m", QASM), eqe.Portal(1, [(0, 1)], [], stamps=backwards), places,
                           clock, max_order=1)
    result = next(e for e in lines if e["event"] == "result")
    assert result["seconds"] is None and result["timestamp_completed"] == "2026-01-05 12:59:59"
    assert code == 2 and lines[-1]["rule"] == "job_time" and "no measured time" in lines[-1]["reason"]
    assert monitor.summary(records_of(places)[0]).seconds >= 0


# --------------------------------------------------------------------- a time below zero at Piast-Q and VLQ

def test_a_piastq_result_collected_by_a_resume_whose_clock_is_behind_holds_no_seconds(tmp_path, places, clock):
    broker = Broker(states=[answer(200, json={"status": "Running"})])
    assert run_broker(tmp_path, places, clock, broker) == 2                     # still Running at wait_seconds
    rec = records_of(places)[0]
    broker.states = [answer(200, json={"status": "Completed"})]
    behind = FakeClock(t=clock.t, start=clock.start - timedelta(hours=1))       # the clock went back an hour
    assert run_broker(tmp_path, places, behind, broker, resume=rec) == 2
    result = events(rec, "result")[-1]
    assert (result["seconds"], result["wall_seconds"], result["recovered"]) == (None, None, True)
    rule = [e for e in events(rec, "rule") if e["rule"] == "job_time"][-1]
    assert (rule["passed"], rule["reason"]) == (False, "the job has no measured time")


def test_vlq_init_node_seconds_below_zero_are_no_measure_and_left_out_of_usage(tmp_path, places, clock):
    def backwards(request: httpx.Request):      # the init job ends before it starts, as across the October change
        if request.url.params["SubmittedJobInfoId"] != "101":
            return None
        return httpx.Response(200, json={"Id": 101, "State": 16, "Tasks": [{"Id": 1010}],
                                         "StartTime": "2026-01-05T12:50:00", "EndTime": "2026-01-05T12:10:00"})

    _fake, m, site = make(tmp_path, places, clock, {"CurrentInfoForJob": backwards})
    assert send(m, site, places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    assert [e["node_seconds"] for e in lines_of(rec) if e.get("step") == "init_status"] == [None]
    (row,) = [row for row in monitor.usage([monitor.summary(rec)], cfg()) if row.startswith("vlq ")]
    assert row.split()[-2:] == ["1", "0.0"]                                   # one init job, no node seconds


# --------------------------------------------------------------------- the guard of a request

def channel(seen: list) -> Channel:
    return Channel(http_client("https://fake.invalid", {}, timeout=1.0, transport=httpx.MockTransport(
        lambda request: seen.append(request) or httpx.Response(200, json={}))))


@pytest.mark.parametrize("method", [b"DELETE", b"GET", None, 7], ids=repr)
def test_a_method_that_is_not_text_is_refused_before_anything_reads_it(method):
    seen = []
    with pytest.raises(UnsafeRequest, match="is never sent: its method is not text"):
        channel(seen).answer(method, "job/1", step="submit")
    assert seen == []
