"""A local file of an odd form is a refusal or a line not read, no traceback."""

import json
import os
from pathlib import Path

import pytest
from fakes import CONFIG, STATE, FakeClock, FakeSite, cfg, lines_of, places_in, records_of, send, write_manifest
from fakes.older import OLDER, START, decide, decisions_file, listed, write

from qdevices import config, lock, manifest, monitor, record, runner
from qdevices.dryrun import dry_run
from qdevices.resolve import resolve
from qdevices.saved_reads import SavedReads
from qdevices.sites import SITES

DEEP = "[" * 100_000 + "]" * 100_000          # JSON nested deeper than the parser goes


def problems_of(path: Path) -> list[str]:
    return manifest.read(path, SITES)[1]


def test_a_manifest_whose_site_is_a_list_is_refused(tmp_path):
    m = write_manifest(tmp_path / "m", site="euroqexa")
    m.write_text(m.read_text().replace('"site": "euroqexa"', '"site": ["euroqexa"]'))
    assert problems_of(m) == ['"site" must be one of euroqexa, vlq, piastq']


def test_a_manifest_whose_options_are_a_list_is_refused_and_the_dry_run_ends_in_failed(tmp_path):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    data = json.loads(m.read_text())
    data["jobs"][0]["options"] = ["no_modify"]
    m.write_text(json.dumps(data))
    assert problems_of(m) == ["job 1: options must be an object"]
    said: list[str] = []
    assert dry_run(m, cfg=cfg(), places=places_in(tmp_path), clock=FakeClock(), say=said.append) == 1
    assert "  FAILED: job 1: options must be an object" in said


def test_a_manifest_nested_too_deep_is_refused(tmp_path):
    m = tmp_path / "manifest.json"
    m.write_text(DEEP)
    assert problems_of(m) == [f"{m} cannot be read as JSON: RecursionError"]


def test_a_job_file_that_cannot_be_read_is_refused(tmp_path, monkeypatch):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    real = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes", lambda self: (_ for _ in ()).throw(PermissionError(13, "denied"))
                        if self.name == "J1.qasm" else real(self))
    assert problems_of(m) == [f"order 1: the file {m.parent / 'J1.qasm'} cannot be read: PermissionError"]


def test_a_config_nested_too_deep_is_a_config_error():
    with pytest.raises(config.ConfigError, match="the config is not TOML: it is nested too deep"):
        config.parse("x = " + "[" * 100_000 + "]" * 100_000)


def test_a_saved_read_nested_too_deep_cannot_be_read(tmp_path):
    path = tmp_path / "read_1.json"
    path.write_text(DEEP)
    assert SavedReads.load(path, "M1") == (None, "cannot be read as JSON")


def test_a_record_line_nested_too_deep_is_a_cut_line(tmp_path):
    path = write(tmp_path / "r" / "run_20260101T100000Z.jsonl", [{"event": "start", "app": "qdevices"}])
    with path.open("a") as fh:
        fh.write(DEEP + "\n")
    lines = record.RecordLines.read(path)
    assert len(lines.events) == 1 and [number for number, _ in lines.cut] == [2]


def test_a_holder_nested_too_deep_or_with_a_pid_above_any_is_handled(places):
    places.state.mkdir(parents=True)
    holder = places.state / "vlq.holder"
    holder.write_text(DEEP)
    with pytest.raises(lock.LockRefused, match="cannot be read"):
        lock.Locks(places.state, host="h").take("vlq")
    holder.write_text(json.dumps({"host": "h", "pid": 2 ** 31, "started": ""}))
    assert "removed" in lock.Locks(places.state, host="h").unlock("vlq", "h")       # no such process


def test_a_lock_file_that_is_a_folder_refuses_the_lock(places):
    (places.state / "vlq.lock").mkdir(parents=True)
    with pytest.raises(lock.LockRefused, match=r"the lock file .* cannot be opened"):
        lock.Locks(places.state, host="h").take("vlq")
    with pytest.raises(lock.LockRefused, match=r"the lock file .* cannot be opened"):
        lock.Locks(places.state, host="h").unlock("vlq", "h")


def test_older_records_whose_home_cannot_be_found_are_unread_for_runs_and_usage_and_refuse_a_send(tmp_path, places,
                                                                                                  clock):
    conf = listed(places, euroqexa=["~no-such-user-of-qdevices/older"])
    error = "~no-such-user-of-qdevices/older cannot be read: its ~ names no home folder here"
    assert monitor.find(places, conf) == [monitor.Unread("~no-such-user-of-qdevices/older", error)]
    shown = monitor.usage(map(monitor.summary, monitor.find(places, conf)), conf)
    assert f"~no-such-user-of-qdevices/older: {error}" in shown
    site = FakeSite()
    with pytest.raises(runner.Refused, match=r"its ~ names no home folder here\. A call that sends needs every"):
        send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), site, places, clock, conf, max_order=1)
    assert not any(call[0] == "submit" for call in site.calls)


def test_a_link_loop_named_like_a_record_is_a_line_that_cannot_be_read(tmp_path, places, clock):
    folder = places.records / "euroqexa" / "m"
    folder.mkdir(parents=True)
    loop = folder / "run_20260101T100000Z.jsonl"
    os.symlink(loop, loop)
    found = monitor.find(places, cfg())
    assert found == [loop] and monitor.run_line(monitor.summary(loop)) == f"{loop}: no record at {loop}"
    with pytest.raises(runner.Refused, match="no record at"):
        send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), FakeSite(), places, clock, max_order=1)


def test_an_award_of_0_hours_gives_no_share_and_no_traceback():
    conf = cfg(CONFIG.replace("[vlq]\n", "[vlq]\naward_hours = 0\n"))
    assert monitor.usage([], conf)[1] == ("vlq: award 0 h = 0 s; 0.0 s measured in the records found (no share of an "
                                          "award of 0 h), 0.0 s counted (no share of an award of 0 h)")


def test_resolve_of_a_record_with_a_utc_of_the_wrong_type_is_refused_and_writes_nothing(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    site = FakeSite(states={"J-1": [STATE("New")]})
    assert send(m, site, places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    rec.write_text(rec.read_text().replace('"event": "status", "utc": "2026-01-05T12:00:00+00:00"',
                                           '"event": "status", "utc": 5'))
    before = rec.read_bytes()
    with pytest.raises(runner.Refused, match="a line holds a value of the wrong type"):
        resolve(rec, 1, None, places=places, clock=clock, host="h")
    assert rec.read_bytes() == before


def test_a_value_with_a_lone_surrogate_is_written_as_its_escape_and_read_back(tmp_path, clock):
    with record.Record(tmp_path / "r.jsonl", clock, {}) as rec:
        rec.write("note", text="a\ud800b")
        rec.write("note", text="café")
    raw = (tmp_path / "r.jsonl").read_bytes()
    assert b"\\ud800" in raw and "café".encode() in raw                     # only that line is escaped
    assert [line["text"] for line in lines_of(tmp_path / "r.jsonl")] == ["a\ud800b", "café"]


def test_resolve_of_an_order_whose_name_holds_a_lone_surrogate_writes_its_decision(tmp_path, places, clock):
    lost = [{"event": "submitting", "order": 2, "name": "K\ud800"}]
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", [START, *OLDER[1:5], *lost])
    conf = listed(places, piastq=[tmp_path / "older"])
    assert "is final with no job" in decide(rec, 2, places, clock, conf)
    assert lines_of(decisions_file(places))[-1]["name"] == "K\ud800"


def test_a_close_that_fails_while_another_error_leaves_keeps_that_error(tmp_path, clock, monkeypatch):
    """An error of the close does not replace the one on its way out."""
    def failing(self):
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(record.Record, "close", failing)
    with pytest.raises(ValueError, match="the error on its way"), record.Record(tmp_path / "r.jsonl", clock, {}):
        raise ValueError("the error on its way")
    with pytest.raises(OSError, match="Input/output error"), record.Record(tmp_path / "r.jsonl", clock, {}):
        pass                                                  # with no other error, a failed close is shown


def test_a_piastq_file_nested_too_deep_is_refused_by_the_check():
    job = {"text": DEEP.encode(), "shots": 10, "options": {}}
    assert SITES["piastq"].validate(job, None) == ["the file is not an operation list of the broker: it is nested "
                                                   "too deep"]


def test_a_dry_run_with_shots_beyond_the_floats_fails_with_its_problem(tmp_path):
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("J1", 10 ** 400),))
    said: list[str] = []
    assert dry_run(m, cfg=cfg(), places=places_in(tmp_path), clock=FakeClock(), say=said.append) == 1
    assert "  FAILED: job 1: shots must be at most 1,000,000,000" in said


def test_a_line_whose_event_is_not_a_text_leaves_its_order_lost_so_it_is_never_sent(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    with open(rec, "a", encoding="utf-8") as fh:
        fh.write('{"event": ["submitting"], "order": 2}\n')
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, max_order=3) == 1
    assert lines_of(rec)[-1]["kind"] == "lost" and not [c for c in site.calls if c[0] == "submit"]
