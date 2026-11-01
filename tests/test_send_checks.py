"""The send loop with a fake site: the checks that refuse a start or stop it before any job is sent."""

import json
from pathlib import Path

import pytest
from fakes import FakeSite, cfg, records_of, send, write_manifest

from qdevices import runner


def test_an_open_order_in_an_older_record_blocks_a_start(tmp_path, places, clock):
    older = tmp_path / "older"
    older.mkdir()
    (older / "run3_20261001T000000Z.jsonl").write_text(
        json.dumps({"event": "submitted", "order": 4, "uuid": "u-4", "machine": "EQE1"}) + "\n")
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "older_records": [str(older)]}
    m = write_manifest(tmp_path / "m")
    with pytest.raises(runner.Refused, match="open or lost"):
        send(m, FakeSite(), places, clock, conf, max_order=1)


@pytest.mark.parametrize("where", ["records", "older"])
def test_a_record_that_cannot_be_read_refuses_the_start(tmp_path, places, clock, where, monkeypatch):
    conf = cfg()
    if where == "records":
        bad = places.records / "euroqexa" / "x" / "run_20260101T000000Z.jsonl"
    else:
        bad = tmp_path / "older" / "run1_20260101T000000Z.jsonl"
        conf["euroqexa"] = {**conf["euroqexa"], "older_records": [str(bad.parent)]}
    bad.parent.mkdir(parents=True)
    bad.write_text("{}\n")
    read_bytes = Path.read_bytes

    def denied(path):
        if path == bad:
            raise PermissionError(13, "Permission denied")
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(runner.Refused, match="cannot be read: PermissionError"):
        send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, conf, max_order=1)


def test_an_older_record_folder_that_does_not_exist_refuses_the_start(tmp_path, places, clock):
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "older_records": [str(tmp_path / "absent")]}
    with pytest.raises(runner.Refused, match="cannot be read"):
        send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, conf, max_order=1)


def test_a_check_against_the_read_that_fails_sends_nothing(tmp_path, places, clock):
    site = FakeSite(problems=["too many qubits"])
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 1
    assert not [c for c in site.calls if c[0] == "submit"]


def test_a_machine_that_is_not_online_stops_before_any_job(tmp_path, places, clock):
    site = FakeSite(read={"machine": "M1", "online": False})
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 2
    assert not [c for c in site.calls if c[0] == "submit"]


def test_a_project_not_in_config_is_refused(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", project="OTHER")
    data = json.loads(m.read_text())
    data["project"] = "OTHER"
    m.write_text(json.dumps(data))
    with pytest.raises(runner.Refused, match="not listed"):
        send(m, FakeSite(), places, clock, max_order=1)


def test_a_vlq_lexis_project_not_in_config_is_refused(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="vlq")
    data = json.loads(m.read_text())
    data["lexis_project"] = "SOMEONE-ELSE"
    m.write_text(json.dumps(data))
    with pytest.raises(runner.Refused, match="lexis_projects"):
        send(m, FakeSite("vlq", seconds_left=3600), places, clock, max_order=1)


def test_a_changed_manifest_or_file_refuses_a_resume(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    rec = records_of(places)[0]
    data = json.loads(m.read_text())
    data["note"] = "changed"
    m.write_text(json.dumps(data))
    with pytest.raises(runner.Refused, match="another manifest"):
        send(m, FakeSite(), places, clock, resume=rec, max_order=2)
    m2 = write_manifest(tmp_path / "m")
    (tmp_path / "m" / "J2.qasm").write_bytes(b"OPENQASM 2.0;\n// changed\n")
    with pytest.raises(runner.Refused, match="SHA-256"):
        send(m2, FakeSite(), places, clock, resume=rec, max_order=2)
