"""`qdevices runs`, `usage` and `jobs` pinned whole, with their exit codes, for a fixed set of records.

`usage` adds a project's records in a loop and a site's projects with sum(); an award of exactly 2**-45 s makes the
percentages exact, so they tell apart two totals that differ only in their last bit.
"""

import json
import re
from pathlib import Path

from fakes import CONFIG, STATE, FakeSite, cfg, lines_of, records_of, send, write_manifest
from fakes.older import OLDER, decide, decisions_file, line_of, main, write

from qdevices import monitor
from qdevices.ledger import Ledger

EQE_FORM = [
    {"event": "start", "machine": "EQE1", "proposal": "TEST-AWARD", "run": "old-run", "jobs": 2,
     "utc": "2026-01-01T10:00:00+00:00"},
    {"event": "submitting", "order": 1, "name": "K1", "machine": "EQE1"},
    {"event": "submitted", "order": 1, "name": "K1", "uuid": "u-1", "machine": "EQE1"},
    {"event": "result", "order": 1, "name": "K1", "uuid": "u-1", "shots": 100, "seconds": 2.5, "machine": "EQE1"},
    {"event": "submitting", "order": 2, "name": "K2", "machine": "EQE1"},
    {"event": "refused", "order": 2, "name": "K2", "http_status": 422, "machine": "EQE1"},
    {"event": "end", "reason": "done", "machine": "EQE1", "utc": "2026-01-01T10:05:00+00:00"},
]
VLQ_FORM = [
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
PIASTQ_FORM = [
    {"event": "start", "machine": "Piast-Q", "proposal": "TEST-AWARD"},
    {"event": "submitting", "order": 1, "name": "K1"},
    {"event": "submitted", "order": 1, "name": "K1", "uid": "p-1"},
    {"event": "result", "order": 1, "name": "K1", "uid": "p-1", "shots": 200, "wall_seconds": 61.0},
    {"event": "submitting", "order": 2, "name": "K2"},
    {"event": "refusal", "order": 2, "name": "K2"},
]
SUMS = ((0.1,), (0.2,), (1 / 3,), (1e-7,), (0.1, 0.2), (0.1, 0.2, 1 / 3, 1e-7))
TOTALS = ((("P1", 0.1), ("P1", 0.2), ("P1", 0.3)), (("P1", 0.1), ("P2", 0.2), ("P3", 0.3)))   # (project, seconds)


def run(places, clock, capsys, *args) -> tuple[int, str]:
    """One command through cli.main: its exit code, and the command with what it printed and its exit code."""
    args = [str(a) for a in args]
    capsys.readouterr()
    code = main(places, clock, *args)
    out, err = capsys.readouterr()
    return code, f"$ qdevices {' '.join(args)}\n{out}" + (f"stderr:\n{err}" if err else "") + f"exit {code}\n"


def fixed_set(tmp_path, places, clock) -> dict:
    """The records of the set by name, the config file that lists the older ones, and two decisions."""
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=2) == 0     # 2 results of 3
    vlq = FakeSite("vlq", seconds_left=3600, states={"J-1": [STATE()]})
    assert send(write_manifest(tmp_path / "v", site="vlq", jobs=(("J1", 10),)), vlq, places, clock, max_order=1) == 2
    euroqexa, open_vlq = records_of(places)                            # the VLQ order is open: the wait timed out
    forms, decided = tmp_path / "older", tmp_path / "decided"
    found = {"euroqexa": euroqexa, "vlq": open_vlq,
             "eqe form": write(forms / "eqe" / "run3_20260101T100000Z.jsonl", EQE_FORM),
             "vlq form": write(forms / "vlq" / "run1_20260101T100000Z.jsonl", VLQ_FORM),
             "piastq form": write(forms / "piastq" / "run1_20260101T100000Z.jsonl", PIASTQ_FORM),
             "decided": write(decided / "batch_20260101T100000Z.jsonl", OLDER)}
    text = (CONFIG.replace("[euroqexa]\n", "[euroqexa]\naward_hours = 1\n")
            .replace("[vlq]\n", f"[vlq]\naward_hours = 10\nolder_records = {json.dumps([str(forms)])}\n")
            .replace("[piastq]\n", f"[piastq]\nolder_records = {json.dumps([str(decided)])}\n"))
    places.config.write_text(text)
    decide(found["decided"], 1, places, clock, cfg(text), "gone")
    decide(found["decided"], 2, places, clock, cfg(text))
    return found


def test_runs_of_the_fixed_set_and_the_line_the_run_10_script_reads(tmp_path, places, clock, capsys, golden):
    found = fixed_set(tmp_path, places, clock)
    code, text = run(places, clock, capsys, "runs", tmp_path / "absent.jsonl")
    golden("monitor_runs", text)
    line = line_of(text.splitlines(), found["vlq"])
    assert code == 0 and re.match("vlq .*open or lost", line)          # as the script greps: '^vlq .*open or lost'


def test_usage_of_the_fixed_set(tmp_path, places, clock, capsys, golden):
    fixed_set(tmp_path, places, clock)
    code, text = run(places, clock, capsys, "usage", tmp_path / "absent.jsonl")
    assert code == 0
    golden("monitor_usage", text)


def test_jobs_of_each_record_of_the_fixed_set(tmp_path, places, clock, capsys, golden):
    found = fixed_set(tmp_path, places, clock)
    done = [run(places, clock, capsys, "jobs", path) for path in found.values()]
    assert [code for code, _ in done] == [0] * len(found)
    golden("monitor_jobs", "".join(text for _, text in done))


def test_runs_usage_and_jobs_with_a_decisions_file_that_cannot_be_read(tmp_path, places, clock, capsys, monkeypatch,
                                                                       golden):
    found = fixed_set(tmp_path, places, clock)
    target, read_bytes = decisions_file(places), Path.read_bytes

    def denied(path):
        if path == target:
            raise PermissionError(13, "Permission denied")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", denied)
    done = [run(places, clock, capsys, *args) for args in (("runs",), ("usage",), ("jobs", found["decided"]))]
    assert [code for code, _ in done] == [0, 0, 0]
    golden("monitor_unreadable_decisions", "".join(text for _, text in done))


def test_runs_usage_and_jobs_with_a_decisions_path_that_is_a_folder(tmp_path, places, clock, capsys, golden):
    found = fixed_set(tmp_path, places, clock)
    target = decisions_file(places)
    target.unlink()
    target.mkdir()
    done = [run(places, clock, capsys, *args) for args in (("runs",), ("usage",), ("jobs", found["decided"]))]
    assert [code for code, _ in done] == [0, 0, 0]
    golden("monitor_decisions_folder", "".join(text for _, text in done))


def results(seconds, project: str = "TEST-PROJECT") -> list[dict]:
    """The lines of a VLQ record of the app, of this project, with one result for each of these seconds."""
    lines = [{"event": "start", "app": "qdevices", "site": "vlq", "project": project, "run": "sums",
              "jobs": len(seconds)}]
    for order, value in enumerate(seconds, 1):
        where = {"order": order, "name": f"J{order}"}
        lines += [{"event": "submitting", **where}, {"event": "submitted", **where, "id": order},
                  {"event": "result", **where, "id": order, "shots": 10, "seconds": value}]
    return lines


def test_the_reprs_of_the_sums_of_seconds(tmp_path, golden):
    conf = cfg()
    conf["vlq"] = {**conf["vlq"], "award_hours": 1}
    rows, summaries = [], []
    for i, seconds in enumerate(SUMS):
        rec = write(tmp_path / f"sums{i}" / "run_20260101T100000Z.jsonl", results(seconds))
        s = monitor.summary(rec)
        summaries.append(s)
        rows.append(f"{seconds!r}: used_seconds {Ledger(lines_of(rec)).used_seconds(100.0)!r}, seconds "
                    f"{s.seconds!r}, counted {s.counted!r}, published {s.published!r}")
    rows += monitor.usage(summaries, conf)
    exact = {**conf, "vlq": {**conf["vlq"], "award_hours": 2 ** -45 / 3600}}     # an award of 2**-45 seconds
    for k, records in enumerate(TOTALS):
        found = [monitor.summary(write(tmp_path / f"totals{k}_{n}" / "run_20260101T100000Z.jsonl",
                                       results((value,), project))) for n, (project, value) in enumerate(records)]
        rows += monitor.usage(found, exact)
    golden("monitor_float_sums", "\n".join(rows) + "\n")
