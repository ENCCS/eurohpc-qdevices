"""Branches of `resolve` and of the monitor that no other test pins, written before W8 moved them."""

import json
from pathlib import Path

import pytest
from fakes import FakeSite, cfg, records_of, send, write_manifest
from fakes.older import OLDER, decide, decisions_file, listed, write

from qdevices import monitor, older, record, runner
from qdevices.resolve import resolve

LONG = b"{" * ((1 << 20) + 1)            # a first line longer than the 1 MiB a reader of an older folder takes


def files_below(root: Path) -> dict:
    """The bytes of every file below `root`, but those of the lock folders."""
    return {p: p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and "state" not in p.relative_to(root).parts}


def lost(tmp_path, places, clock) -> Path:
    """A record of the app whose order 1 is lost."""
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, FakeSite(submits={1: ("noanswer",)}), places, clock, max_order=1) == 2
    return records_of(places)[0]


def test_the_runs_line_counts_results_with_no_seconds_and_cut_lines(tmp_path, places, clock):
    where = {"order": 1, "name": "J1"}
    rec = write(places.records / "vlq" / "m" / "run_20260101T100000Z.jsonl",
                [{"event": "start", "app": "qdevices", "site": "vlq", "project": "TEST-PROJECT", "jobs": 1,
                  "utc": "2026-01-01T10:00:00+00:00"}, {"event": "submitting", **where},
                 {"event": "submitted", **where, "id": 7}, {"event": "result", **where, "id": 7, "shots": 10},
                 {"event": "end", "reason": "done", "utc": "2026-01-01T10:00:02+00:00"}])
    with rec.open("a", encoding="utf-8") as fh:
        fh.write('{"event": "status", "or')                   # a cut last line
    line = monitor.run_line(monitor.summary(rec))
    assert line == (f"vlq  TEST-PROJECT  m  {rec}: 1 results of 1 jobs; 0.0 s measured; "
                    "1 results with no seconds; 0.0 s by the published rule; 1 cut lines; "
                    "2026-01-01T10:00:00Z to 2026-01-01T10:00:02Z; end: done")


def test_a_decisions_file_keeps_only_resolved_lines_with_a_start_digest(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    decide(rec, 2, places, clock, listed(places, piastq=[tmp_path / "older"]))
    target = decisions_file(places)
    kept = json.loads(target.read_text(encoding="utf-8"))
    with target.open("a", encoding="utf-8") as fh:
        for line in ({**kept, "start_sha256": 5}, {**kept, "event": "note"}, {k: v for k, v in kept.items()
                                                                            if k != "start_sha256"}):
            fh.write(json.dumps(line) + "\n")
    assert older.Decisions.load(places.records).by_start == {kept["start_sha256"]: [kept]}


@pytest.mark.parametrize("given", [cfg(), None])
def test_an_unknown_decision_on_a_record_of_the_app_is_an_error_of_the_program(tmp_path, places, clock, given):
    rec = lost(tmp_path, places, clock)
    places.config.write_text("")
    before = files_below(tmp_path)
    with pytest.raises(ValueError) as caught:
        resolve(rec, 1, None, places=places, clock=clock, host="host-a", decision="later", cfg=given)
    assert str(caught.value) == "no decision 'later'" and files_below(tmp_path) == before


def test_an_unknown_decision_on_a_record_of_the_app_reads_the_config_first(tmp_path, places, clock):
    rec = lost(tmp_path, places, clock)
    places.config.write_text("[euroqexa\n")
    with pytest.raises(runner.Refused) as refused:
        resolve(rec, 1, None, places=places, clock=clock, host="host-a", decision="later")
    assert str(refused.value).startswith("the config is not TOML: ")


def test_an_unknown_decision_on_a_record_of_another_runner_is_an_error_of_the_program(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    conf = listed(places, piastq=[tmp_path / "older"])
    before = files_below(tmp_path)
    with pytest.raises(ValueError) as caught:
        decide(rec, 2, places, clock, conf, "later")
    assert str(caught.value) == "no decision 'later'" and files_below(tmp_path) == before
    assert decide(rec, 2, places, clock, conf).startswith("order 2 of ")       # the lock was released


def test_a_place_whose_home_cannot_be_found_holds_no_record(tmp_path, places, clock):
    folder = tmp_path / "older"
    rec = write(folder / "run1_20260101T100000Z.jsonl", OLDER)
    alone = listed(places, piastq=["~no-such-user-of-qdevices/older"])
    with pytest.raises(runner.Refused) as refused:
        decide(rec, 2, places, clock, alone)
    assert "and no older_records in qdevices.toml hold it." in str(refused.value)
    beside = listed(places, piastq=["~no-such-user-of-qdevices/older", folder])
    assert decide(rec, 2, places, clock, beside) == (f"order 2 of {rec} is final with no job. The decision is in "
                                                      f"{decisions_file(places)}; the record of the other runner is "
                                                      "not written")


def test_a_place_that_cannot_be_read_holds_no_record(tmp_path, places, clock):
    folder = tmp_path / "older"
    rec = write(folder / "run1_20260101T100000Z.jsonl", OLDER)
    (folder / "batch.jsonl").write_bytes(LONG)                # its first line cannot be read
    with pytest.raises(runner.Refused) as refused:
        decide(rec, 2, places, clock, listed(places, piastq=[folder]))
    assert "and no older_records in qdevices.toml hold it." in str(refused.value)
    assert not decisions_file(places).exists()


def test_a_place_with_a_tilde_is_read_below_home(tmp_path, places, clock, monkeypatch):
    home = tmp_path / "home"
    rec = write(home / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    monkeypatch.setenv("HOME", str(home))
    conf = listed(places, piastq=["~/older"])
    assert monitor.find(places, conf) == [rec]
    assert decide(rec, 2, places, clock, conf).startswith(f"order 2 of {rec} is final with no job.")


def test_a_path_with_a_tilde_is_taken_as_given(tmp_path, places, clock, monkeypatch):
    home = tmp_path / "home"
    write(home / "older" / "run1_20260101T100000Z.jsonl", OLDER)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(tmp_path)
    found = monitor.find(places, cfg(), ["~/older"])
    assert found == [monitor.Unread(str(tmp_path / "~" / "older"),
                                    f"{Path('~/older')} cannot be read: FileNotFoundError")]


def test_a_record_of_the_app_names_the_site_of_its_own_lines(tmp_path, places, clock):
    rec = lost(tmp_path, places, clock)
    assert resolve(rec, 1, None, places=places, clock=clock, host="host-a") == "order 1 is final with no job"
    assert json.loads(rec.read_text(encoding="utf-8").splitlines()[-1])["site"] == "euroqexa"
    assert record.RecordLines.read(rec).cut == []


@pytest.mark.parametrize("starts, rows", [
    ([{"project": ["P"]}], ["vlq       ['P']  "]),
    ([{"project": 5}, {"project": "A"}], ["vlq       5      ", "vlq       A      "])])
def test_a_start_line_with_a_project_of_another_type_is_shown_as_text_by_usage(tmp_path, starts, rows):
    """Fault 19 of the plan, fixed: a project that is a list, or projects of two types, ended usage in a TypeError."""
    paths = [write(tmp_path / f"r{i}" / "run_20260101T100000Z.jsonl",
                   [{"event": "start", "app": "qdevices", "site": "vlq", **start}]) for i, start in enumerate(starts)]
    lines = monitor.usage([monitor.summary(p) for p in paths], cfg())
    assert [line[:17] for line in lines[1:1 + len(rows)]] == rows


def test_a_start_line_whose_lists_is_no_text_is_a_record_that_cannot_be_read(tmp_path):
    """Fault 19 of the plan, fixed: it ended runs and usage in a TypeError; now its line says why it is not read."""
    path = write(tmp_path / "r" / "run_20260101T100000Z.jsonl",
                 [{"event": "start", "app": "qdevices", "site": "vlq", "lists": 7}])
    found = monitor.summary(path)
    assert monitor.run_line(found) == f"{path}: a line holds a value of the wrong type (TypeError)"
    assert monitor.usage([found], cfg())[1:3] == [monitor.run_line(found), "The records and folders above cannot be "
                                                                            "read: they are not in the totals."]


def test_a_vlq_job_id_of_digits_that_int_refuses_is_kept_as_text(tmp_path, places, clock):
    """Fault 20, fixed: "²" passes isdigit and is no number, so it is kept as a text id, as any other text is."""
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("J1", 10),))
    assert send(m, FakeSite("vlq", seconds_left=3600, submits={1: ("noanswer",)}), places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    with rec.open("a", encoding="utf-8") as fh:
        fh.write('{"event": "status", "or')
    before = rec.read_bytes()
    said = resolve(rec, 1, "²", places=places, clock=clock, host="host-a")
    assert said == "order 1 has the job ²; a resume collects it"
    assert rec.read_bytes().startswith(before + b"\n")
    assert json.loads(rec.read_text(encoding="utf-8").splitlines()[-1])["id"] == "²"
