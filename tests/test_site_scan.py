"""The records a send reads: what, in what order, what refuses a call."""

import json
import os
from pathlib import Path

import pytest
from fakes import FakeSite, cfg, lines_of, send, write_manifest
from fakes.older import LOST, OLDER, OPEN, START, decide, decisions_file, listed, piastq_send, write

from qdevices import older, runner
from qdevices.ledger import Ledger
from qdevices.record import RecordError
from qdevices.runner import preflight
from qdevices.values import is_int, sha256_hex

APP_NAME = "run_20260101T000000Z.jsonl"           # the form of the name of a record of the app
LATER_NAME = "run_20260102T000000Z.jsonl"
PROJECT = "TEST-PROJECT"
NEEDS = "A call that sends needs every record of the site readable"
LONE = chr(0xD800)                                # a lone surrogate; json.dumps writes it as a backslash escape
NO_SITE = [{"event": "start", "proposal": "TEST-AWARD"}, *OPEN]
VLQ_OPEN = [{"event": "start", "machine": "VLQ", "project": "TEST-LEXIS"},
            {"event": "submitting", "order": 1, "name": "V1"},
            {"event": "submitted", "order": 1, "name": "V1", "job": 502}]


def scanned(places, site, site_config) -> list[tuple[Path, list[dict], bool]]:
    """The records a send reads: (path, lines, older)."""
    return [(s.path, s.ledger.events, s.older) for s in preflight.SiteScan.read(places, site, site_config).scans]


def readable(places, site, site_config) -> list[tuple[Path, list[dict], bool]]:
    """The records a send reads, or Refused for one that cannot be read."""
    return [(s.path, s.ledger.events, s.older) for s in preflight.SiteScan.readable(places, site, site_config).scans]


def _site_scan(scans) -> preflight.SiteScan:
    """A SiteScan of what `scanned` gave."""
    return preflight.SiteScan([preflight.Scan(path, Ledger(lines), is_older) for path, lines, is_older in scans])


def blocking(scans) -> list[str]:
    """The text of each open or lost order of what `scanned` gave."""
    return _site_scan(scans).blockers()


def elsewhere(scans, here, project, limit) -> float:
    """The seconds of what `scanned` gave, for the budget of the record at `here`."""
    return _site_scan(scans).used_elsewhere(here, project, limit)


def at(places, *where) -> dict:
    """The config of Piast-Q with these places of older_records."""
    return listed(places, piastq=where)["piastq"]


def merged(places, lines: list[dict]) -> list[dict]:
    """These lines with the decisions of Piast-Q that bind them."""
    return older.Decisions.load(places.records, ("piastq",)).merged(lines)


def decision_on(lines: list[dict], job_id) -> dict:
    """A --gone on order 1 of these lines, as a decisions file of Piast-Q holds it."""
    return {"event": "resolved", "app": "qdevices", "site": "piastq", "order": 1, **older.binding(lines),
            "decided_id": job_id, "gone": True, "counted_seconds": 100.0}


def one_result(seconds: float, **start) -> list[dict]:
    """A start line with these keys, then one order with a result of these seconds."""
    where = {"order": 1, "name": "J1"}
    return [{"event": "start", **start}, {"event": "submitting", **where}, {"event": "submitted", **where, "id": "J-1"},
            {"event": "result", **where, "id": "J-1", "shots": 10, "seconds": seconds}]


def bound(lines: list[dict]) -> bytes:
    """These lines as a decision binds them: canonical JSON, each with a new line, surrogates by surrogatepass."""
    texts = (json.dumps(line, sort_keys=True, separators=(",", ":"), ensure_ascii=False) for line in lines)
    return "".join(text + "\n" for text in texts).encode("utf-8", "surrogatepass")


def refuse_stat(monkeypatch, path: Path) -> None:
    """Path.stat of `path` raises PermissionError."""
    stat = Path.stat

    def denied(self, *, follow_symlinks=True):
        if self == path:
            raise PermissionError(13, "Permission denied", str(self))
        return stat(self, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(Path, "stat", denied)


def refuse_listing(monkeypatch, folder: Path) -> None:
    """os.scandir of `folder`, which os.walk calls, raises PermissionError."""
    scandir = os.scandir

    def denied(path="."):
        if not isinstance(path, int) and Path(path) == folder:
            raise PermissionError(13, "Permission denied", str(path))
        return scandir(path)

    monkeypatch.setattr(os, "scandir", denied)


def test_an_older_place_written_with_a_tilde_is_read_below_the_home_folder(tmp_path, places, monkeypatch):
    home = tmp_path / "home"
    rec = write(home / "older" / "run1.jsonl", OLDER)
    monkeypatch.setenv("HOME", str(home))
    assert scanned(places, "piastq", at(places, "~/older")) == [(rec, lines_of(rec), True)]


def test_a_send_is_refused_with_the_text_of_the_decisions_file_when_the_run_folder_cannot_be_read_either(
        tmp_path, places, clock, monkeypatch):
    folder, target = places.records / "piastq", decisions_file(places)
    folder.mkdir(parents=True)
    conf = listed(places, piastq=[tmp_path / "older"])
    manifest = write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 10),))
    site = FakeSite("piastq")
    refuse_listing(monkeypatch, folder)
    with monkeypatch.context() as both:
        refuse_stat(both, target)
        with pytest.raises(runner.Refused) as refused:
            send(manifest, site, places, clock, conf, max_order=1)
    assert str(refused.value).startswith(f"{target} cannot be read: PermissionError. {NEEDS}")
    assert f"{folder} cannot be read" not in str(refused.value) and site.calls == []
    with pytest.raises(runner.Refused) as refused:       # the stat passes: the listing is next, and it is refused
        send(manifest, site, places, clock, conf, max_order=1)
    assert str(refused.value).startswith(f"{folder} cannot be read: PermissionError. {NEEDS}")
    assert site.calls == []


def test_a_site_with_no_older_records_does_not_read_its_decisions_file(tmp_path, places, clock, monkeypatch):
    refuse_stat(monkeypatch, decisions_file(places))
    conf = cfg()
    assert scanned(places, "piastq", conf["piastq"]) == []
    assert readable(places, "piastq", conf["piastq"]) == []
    assert piastq_send(tmp_path, places, clock, conf) == 0


def test_a_stat_of_the_decisions_file_that_fails_is_a_record_error_with_its_path(tmp_path, places, monkeypatch):
    target = decisions_file(places)
    site_config = at(places, tmp_path / "older")
    refuse_stat(monkeypatch, target)
    with pytest.raises(RecordError) as raised:
        scanned(places, "piastq", site_config)
    assert raised.value.path == target and str(raised.value) == f"{target} cannot be read: PermissionError"
    with pytest.raises(runner.Refused, match=NEEDS) as refused:
        readable(places, "piastq", site_config)
    assert str(refused.value).startswith(f"{target} cannot be read: PermissionError. ")


def test_a_stat_of_the_records_folder_of_the_site_that_fails_is_a_record_error_and_no_job_is_sent(
        tmp_path, places, clock, monkeypatch):
    folder = places.records / "piastq"
    folder.mkdir(parents=True)
    conf = cfg()
    refuse_stat(monkeypatch, folder)
    with pytest.raises(RecordError) as raised:
        scanned(places, "piastq", conf["piastq"])
    assert Path(raised.value.path) == folder and str(raised.value) == f"{folder} cannot be read: PermissionError"
    with pytest.raises(runner.Refused, match=NEEDS):
        readable(places, "piastq", conf["piastq"])
    site = FakeSite("piastq")
    with pytest.raises(runner.Refused, match=NEEDS) as refused:
        send(write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 10),)), site, places, clock, conf, max_order=1)
    assert str(refused.value).startswith(f"{folder} cannot be read: PermissionError. ") and site.calls == []


def test_no_records_folder_of_the_site_is_no_error(places):
    assert not (places.records / "piastq").exists()
    assert scanned(places, "piastq", at(places)) == []


def test_an_older_jsonl_that_is_a_broken_link_not_named_run_cannot_be_read(tmp_path, places):
    link = tmp_path / "older" / "batch.jsonl"
    link.parent.mkdir()
    link.symlink_to(tmp_path / "absent")
    with pytest.raises(RecordError) as raised:
        scanned(places, "piastq", at(places, link.parent))
    assert raised.value.path == link and str(raised.value) == f"{link} cannot be read: FileNotFoundError"


def test_an_older_jsonl_that_is_a_broken_link_named_run_is_listed_and_then_no_record(tmp_path, places):
    link = tmp_path / "older" / "run1.jsonl"
    link.parent.mkdir()
    link.symlink_to(tmp_path / "absent")
    with pytest.raises(RecordError) as raised:
        scanned(places, "piastq", at(places, link.parent))
    assert raised.value.path == link and str(raised.value) == f"no record at {link}"


def test_an_older_fifo_not_named_run_is_passed_over_with_no_error_and_no_blocking(tmp_path, places):
    folder = tmp_path / "older"
    folder.mkdir()
    os.mkfifo(folder / "pipe.jsonl")
    scans = scanned(places, "piastq", at(places, folder))
    assert scans == [] and blocking(scans) == []


def test_an_older_fifo_named_run_is_listed_and_then_no_record(tmp_path, places):
    fifo = tmp_path / "older" / "run1.jsonl"
    fifo.parent.mkdir()
    os.mkfifo(fifo)
    with pytest.raises(RecordError) as raised:
        scanned(places, "piastq", at(places, fifo.parent))
    assert raised.value.path == fifo and str(raised.value) == f"no record at {fifo}"


def test_a_line_with_a_lone_surrogate_is_kept_and_a_decision_on_its_record_binds(tmp_path, places, clock):
    rec = write(tmp_path / "older" / "run1.jsonl", [{**START, "note": LONE}, *OPEN, {**LOST[0], "name": LONE}])
    assert rec.read_bytes().isascii() and json.dumps(LONE).encode() in rec.read_bytes()     # the escape, as written
    conf = listed(places, piastq=[rec.parent])
    scans = scanned(places, "piastq", conf["piastq"])
    [(path, lines, is_older)] = scans
    assert (path, is_older) == (rec, True) and lines[0]["note"] == lines[-1]["name"] == LONE
    assert blocking(scans) == [f"{rec}: order 1 is open", f"{rec}: order 2 is lost"]
    binding = older.binding(lines)
    assert binding["lines_sha256"] == sha256_hex(bound(lines))
    assert binding["start_sha256"] == sha256_hex(bound(lines[:1])[:-1])
    decide(rec, 1, places, clock, conf, "gone")                # order 1 has a plain name: it is written in the line
    [decision] = lines_of(decisions_file(places))
    assert {key: decision[key] for key in binding} == binding
    scans = scanned(places, "piastq", conf["piastq"])
    assert scans == [(rec, [*lines, decision], True)]
    assert blocking(scans) == [f"{rec}: order 2 is lost"]


def test_an_older_record_of_another_machine_is_passed_over_even_with_a_decision_of_this_site(tmp_path, places):
    lines = lines_of(write(tmp_path / "older" / "run1.jsonl", VLQ_OPEN))
    decision = decision_on(lines, 502)
    write(decisions_file(places), [decision])
    assert merged(places, lines) == [*lines, decision]         # it binds, and it holds the site
    assert scanned(places, "piastq", at(places, tmp_path / "older")) == []


def test_an_older_record_with_no_site_that_can_be_told_is_read_with_its_decisions(tmp_path, places):
    rec = write(tmp_path / "older" / "run1.jsonl", NO_SITE)
    lines = lines_of(rec)
    decision = decision_on(lines, "p-1")
    write(decisions_file(places), [decision])
    assert scanned(places, "piastq", at(places, tmp_path / "older")) == [(rec, [*lines, decision], True)]


def test_a_record_of_the_app_folder_is_read_whatever_it_names_and_is_never_merged(tmp_path, places):
    rec = write(places.records / "piastq" / "x" / APP_NAME,
                [{"event": "start", "site": "vlq", "machine": "VLQ"}, *OPEN])
    lines = lines_of(rec)
    decision = decision_on(lines, "p-1")
    write(decisions_file(places), [decision])
    (tmp_path / "older").mkdir()
    assert merged(places, lines) == [*lines, decision]         # it would bind: the start line holds no "app"
    assert scanned(places, "piastq", at(places, tmp_path / "older")) == [(rec, lines, False)]


def test_the_app_comes_first_by_folder_and_name_then_each_place_in_the_order_of_the_config_each_record_once(
        tmp_path, places):
    folder, late, early = places.records / "piastq", tmp_path / "z", tmp_path / "a"
    app = [write(folder / where / name, OLDER) for where, name in (("a", APP_NAME), ("a", LATER_NAME),
                                                                   ("a/b", APP_NAME), ("c", APP_NAME))]
    first = write(late / "run1.jsonl", OLDER)
    below = write(late / "sub" / "run2.jsonl", OLDER)
    linked = write(early / "run3.jsonl", OLDER)
    alone = write(early / "run4.jsonl", OLDER)
    link = late / "run0.jsonl"
    link.symlink_to(linked)                                    # the first place: it stands for run3 of the second
    scans = scanned(places, "piastq", at(places, late, early, late / "sub", folder))    # the app's records again
    assert [(path, is_older) for path, _, is_older in scans] == [*[(path, False) for path in app], (link, True),
                                                                 (first, True), (below, True), (alone, True)]


def test_blocking_gives_one_text_for_each_open_or_lost_order_in_the_order_of_the_scans_each_by_number(tmp_path, places):
    app = write(places.records / "piastq" / "x" / APP_NAME,
                [{"event": "submitting", "order": 3, "name": "J3"},
                 {"event": "submitting", "order": 1, "name": "J1"},
                 {"event": "submitted", "order": 1, "name": "J1", "id": "J-1"},
                 {"event": "submitted", "order": 2, "name": "J2", "id": "J-2"},
                 {"event": "result", "order": 2, "name": "J2", "id": "J-2", "seconds": 1.0}])
    other = write(tmp_path / "older" / "run1.jsonl", OLDER)
    scans = scanned(places, "piastq", at(places, tmp_path / "older"))
    assert blocking(scans) == [f"{app}: order 1 is open", f"{app}: order 3 is lost",
                               f"{other}: order 1 is open", f"{other}: order 2 is lost"]


def test_an_older_record_counts_whatever_its_project_and_one_of_the_app_only_by_its_first_project(tmp_path, places):
    folder, place = places.records / "piastq", tmp_path / "older"
    write(place / "run1.jsonl", one_result(1.0, machine="Piast-Q", project="OTHER"))
    write(place / "run2.jsonl", one_result(2.0))
    same = write(folder / "same" / APP_NAME, one_result(4.0, project=PROJECT))
    write(folder / "other" / APP_NAME, one_result(8.0, project="OTHER"))
    write(folder / "award" / APP_NAME, one_result(16.0, proposal=PROJECT))
    write(folder / "late" / APP_NAME, [*one_result(32.0, project=""), {"event": "end", "project": PROJECT}])
    write(folder / "first" / APP_NAME, [*one_result(64.0, project="OTHER"), {"event": "end", "project": PROJECT}])
    scans = scanned(places, "piastq", at(places, place))
    assert elsewhere(scans, (tmp_path / "none").resolve(), PROJECT, 100.0) == 39.0     # 1 + 2 + 4 + 32
    assert elsewhere(scans, same.resolve(), PROJECT, 100.0) == 35.0


def test_with_nothing_to_add_the_seconds_elsewhere_are_the_int_0(tmp_path, places):
    no_record = elsewhere(scanned(places, "piastq", at(places)), (tmp_path / "none").resolve(), PROJECT, 100.0)
    rec = write(places.records / "piastq" / "x" / APP_NAME, one_result(1.0, project=PROJECT))
    scans = scanned(places, "piastq", at(places))
    left_out = elsewhere(scans, rec.resolve(), PROJECT, 100.0)
    other_project = elsewhere(scans, (tmp_path / "none").resolve(), "OTHER", 100.0)
    assert all(is_int(value) and value == 0 for value in (no_record, left_out, other_project))


def test_ten_records_of_a_tenth_of_a_second_add_up_as_sum_of_floats_does(tmp_path, places):
    for n in range(10):
        write(places.records / "piastq" / f"r{n}" / APP_NAME, one_result(0.1, project=PROJECT))
    scans = scanned(places, "piastq", at(places))
    assert elsewhere(scans, (tmp_path / "none").resolve(), PROJECT, 100.0) == sum([0.1] * 10)     # not a += loop
