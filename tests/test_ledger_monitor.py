"""The ledger and the monitor, on synthetic records in this app's form and in the forms of the older runners."""

import json

from fakes import FakeSite, cfg, places_in, records_of, send, write_manifest

from qdevices import monitor
from qdevices.ledger import Ledger


def write(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


OLDER_EQE = [
    {"event": "start", "machine": "EQE1", "proposal": "TEST-AWARD", "run": "old-run", "jobs": 2,
     "utc": "2026-01-01T10:00:00+00:00"},
    {"event": "submitting", "order": 1, "name": "K1", "machine": "EQE1"},
    {"event": "submitted", "order": 1, "name": "K1", "uuid": "u-1", "machine": "EQE1"},
    {"event": "result", "order": 1, "name": "K1", "uuid": "u-1", "shots": 100, "seconds": 2.5, "machine": "EQE1"},
    {"event": "submitting", "order": 2, "name": "K2", "machine": "EQE1"},
    {"event": "refused", "order": 2, "name": "K2", "http_status": 422, "machine": "EQE1"},
    {"event": "end", "reason": "done", "machine": "EQE1", "utc": "2026-01-01T10:05:00+00:00"},
]
OLDER_VLQ = [
    {"event": "start", "machine": "VLQ", "project": "TEST-LEXIS", "jobs": 3},
    {"event": "init", "order": 1, "step": "created", "job": 501},
    {"event": "submitting", "order": 1, "name": "V1"},
    {"event": "submitted", "order": 1, "name": "V1", "job": 502, "step": "created"},
    {"event": "submitted", "order": 1, "name": "V1", "job": 502, "step": "submitted"},
    {"event": "result", "order": 1, "name": "V1", "job": 502, "shots": 100, "device_seconds": 0.23},
    {"event": "init", "order": 2, "step": "created", "job": 503},
    {"event": "submitting", "order": 2, "name": "K1"},
    {"event": "submitted", "order": 2, "name": "K1", "job": 504, "step": "created"},
    {"event": "stop", "order": 2, "job": 504, "kind": "upload_error"},
    {"event": "init", "order": 3, "step": "created", "job": 505},
    {"event": "submitting", "order": 3, "name": "K2"},
    {"event": "submitted", "order": 3, "name": "K2", "job": 506, "step": "created"},
    {"event": "stop", "order": 3, "job": 506, "kind": "submit_error", "http_status": 504},
    {"event": "stop", "order": 3, "job": 506, "kind": "not_submitted"},
]
OLDER_PIASTQ = [
    {"event": "start", "machine": "Piast-Q", "proposal": "TEST-AWARD"},
    {"event": "submitting", "order": 1, "name": "K1"},
    {"event": "submitted", "order": 1, "name": "K1", "uid": "p-1"},
    {"event": "result", "order": 1, "name": "K1", "uid": "p-1", "shots": 200, "wall_seconds": 61.0},
    {"event": "submitting", "order": 2, "name": "K2"},
    {"event": "refusal", "order": 2, "name": "K2"},
]


def test_the_ledger_reads_the_older_forms():
    eqe = Ledger(OLDER_EQE).orders
    assert eqe[1].status == "final" and eqe[2].final == "refused"
    vlq = Ledger(OLDER_VLQ).orders
    assert vlq[1].final == "result"
    assert vlq[2].final == "never_submitted"               # created, an upload failed: it cannot run
    assert vlq[3].status == "open"                         # a submission with a 504 may still be at work
    piastq = Ledger(OLDER_PIASTQ).orders
    assert piastq[2].final == "refusal"
    assert Ledger(OLDER_PIASTQ).site == "piastq"


def test_runs_jobs_and_usage_of_older_records(tmp_path):
    places = places_in(tmp_path)
    conf = cfg()
    conf["vlq"] = {**conf["vlq"], "award_hours": 10, "older_records": [str(tmp_path / "older")]}
    write(tmp_path / "older" / "eqe" / "run3_20260101T100000Z.jsonl", OLDER_EQE)
    write(tmp_path / "older" / "vlq" / "run1_20260101T100000Z.jsonl", OLDER_VLQ)
    write(tmp_path / "older" / "piastq" / "run1_20260101T100000Z.jsonl", OLDER_PIASTQ)
    summaries = [monitor.summary(p) for p in monitor.find(places, conf)]
    by_site = {s.site: s for s in summaries}
    assert by_site["euroqexa"].seconds == 2.5 and by_site["euroqexa"].results == 1
    assert by_site["vlq"].init_jobs == 3 and by_site["vlq"].published == 0.9
    assert by_site["vlq"].open == [(3, "open")]
    assert by_site["piastq"].seconds == 61.0
    lines = [monitor.run_line(s) for s in summaries]
    assert any("open or lost: order 3 open" in line for line in lines)
    table = monitor.usage(summaries, conf)
    assert any(line.startswith("vlq: award 10 h") for line in table)
    rows = monitor.job_rows(OLDER_EQE)
    assert any("u-1" in row for row in rows) and any("refused" in row for row in rows)


def test_usage_counts_init_jobs_and_their_node_time():
    lines = [{"event": "init", "order": 1, "step": "init_created", "init_job": 9},
             {"event": "init", "order": 1, "step": "init_status", "init_job": 9, "node_seconds": 12.0},
             {"event": "init", "order": 2, "step": "init_created", "init_job": 11}]
    assert monitor.init_jobs(lines) == (2, 12.0, 1)


def test_the_monitor_reads_this_apps_records(tmp_path, places, clock):
    send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=2)
    s = monitor.summary(records_of(places)[0])
    assert s.site == "euroqexa" and s.results == 2 and s.seconds == 3.0 and s.manifest_jobs == 3
