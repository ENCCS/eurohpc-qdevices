"""A resume names the job id that a cut line holds, and says when the id itself may be cut."""

import json

import pytest
from fakes import FakeSite, cfg, lines_of, records_of, send, write_manifest

from qdevices import record, runner

SUBMITTED = {"event": "submitted", "utc": "2026-01-05T12:00:01+00:00", "app": "qdevices", "site": "euroqexa",
             "machine": "M1", "project": "TEST-PROJECT", "order": 1, "name": "J1", "id": "J-4711",
             "submitted_utc": "2026-01-05T12:00:01+00:00"}


def append_cut(rec, cut: str) -> int:
    """Append a line cut by a crash, with no newline; its line number."""
    number = len(lines_of(rec)) + 1
    with open(rec, "a") as fh:
        fh.write(cut)
    return number


def resume(m, places, clock, rec, said: list) -> int:
    return runner.send(m, FakeSite(), cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="host-a",
                       say=said.append, resume=rec)


def last(rec, kind: str) -> dict:
    return [e for e in record.RecordLines.read(rec).events if e["event"] == kind][-1]


@pytest.mark.parametrize("end, job_id, may_be_cut", [
    ('"submitted_utc": "2026-01', "J-4711", False),       # a crash in the write of the time: the id is whole
    ('"id": "J-47', "J-47", True),                         # a crash in the write of the id
])
def test_a_resume_names_the_job_id_of_a_cut_submitted_line(tmp_path, places, clock, end, job_id, may_be_cut):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(submits={1: ("interrupt",)}), places, clock, max_order=1) == 130
    rec = records_of(places)[0]
    text = json.dumps(SUBMITTED)
    cut = text[:text.index(end) + len(end)]
    number = append_cut(rec, cut)
    said = []
    assert resume(m, places, clock, rec, said) == 1                  # the order stays lost
    note = f"NOTE: line {number} holds the job id {job_id}"
    assert (note + "; the id may be cut, as the line ends in it" if may_be_cut else note) in said
    assert last(rec, "resume")["cut_lines"] == [{"line": number, "text": cut[:120], "job_id": job_id,
                                                 "job_id_may_be_cut": may_be_cut}]
    assert last(rec, "stop")["kind"] == "lost"


def test_a_cut_line_with_no_job_id_gives_only_the_note_of_the_cut(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    cut = '{"event": "rule", "utc": "2026-01-05T12:00:09+00:00", "id": null, "rule": "sho'
    number = append_cut(rec, cut)
    said = []
    assert resume(m, places, clock, rec, said) == 0
    assert [s for s in said if s.startswith("NOTE: line")] == [
        f"NOTE: line {number} of the record is cut and is not read: {cut}"]
    assert last(rec, "resume")["cut_lines"] == [{"line": number, "text": cut}]
