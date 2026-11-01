"""Each line of a record is read as UTF-8 on its own: a line cut inside a character is a cut line, nothing more."""

from fakes import FakeClock, FakeSite, records_of, send, write_manifest

from qdevices import record

E = chr(0xE9)                         # two bytes in UTF-8
REPLACEMENT = chr(0xFFFD)


def cut_inside_a_character(text: str) -> bytes:
    """The UTF-8 bytes of a text that ends in E, less the last byte: a crash inside the write of E."""
    return (text + E).encode("utf-8")[:-1]


def test_a_line_cut_inside_a_character_is_a_cut_line(tmp_path):
    path = tmp_path / "run_20260101T000000Z.jsonl"
    rec = record.Record(path, FakeClock(), {"site": "vlq"})
    rec.write("start", note="caf" + E)
    rec.close()
    with open(path, "ab") as fh:
        fh.write(cut_inside_a_character('{"event": "status", "order": 1, "id": 12, "body": "caf'))
    rec = record.Record(path, FakeClock(), {"site": "vlq"})
    rec.write("resume", note="caf" + E)
    rec.close()
    events, cut = record.RecordLines.read(path)
    assert [(e["event"], e["note"]) for e in events] == [("start", "caf" + E), ("resume", "caf" + E)]
    assert cut == [(2, '{"event": "status", "order": 1, "id": 12, "body": "caf' + REPLACEMENT)]


def test_a_record_with_such_a_line_lets_a_resume_send(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    with open(rec, "ab") as fh:
        fh.write(cut_inside_a_character('{"event": "status", "order": 1, "body": "caf'))
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, max_order=2) == 0
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 2)]
    events, cut = record.RecordLines.read(rec)
    assert len(cut) == 1 and cut[0][1].endswith("caf" + REPLACEMENT)
    assert events[-1]["event"] == "end"
