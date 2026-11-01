"""The older records a send reads: each record once, and only those of its own site or of no site that can be told."""

import json

import pytest
from fakes import FakeSite, cfg, send, write_manifest

from qdevices import runner
from qdevices.runner.preflight import SiteScan

OPEN_VLQ = [{"event": "start", "machine": "VLQ", "project": "TEST-LEXIS"},
            {"event": "submitting", "order": 1, "name": "V1"},
            {"event": "submitted", "order": 1, "name": "V1", "job": 502, "step": "submitted"}]
OPEN_UNKNOWN = [{"event": "submitting", "order": 1, "name": "K1"},
                {"event": "submitted", "order": 1, "name": "K1", "uuid": "u-9"}]
EQE_600 = [{"event": "start", "machine": "EQE1", "proposal": "TEST-AWARD"},
           {"event": "submitting", "order": 1, "name": "K1", "machine": "EQE1"},
           {"event": "submitted", "order": 1, "name": "K1", "uuid": "u-1", "machine": "EQE1"},
           {"event": "result", "order": 1, "name": "K1", "uuid": "u-1", "shots": 100, "seconds": 600.0,
            "machine": "EQE1"}]


def write(path, lines):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


def with_older(*folders) -> dict:
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "older_records": [str(f) for f in folders]}
    return conf


def test_an_older_record_of_another_site_is_passed_over(tmp_path, places, clock):
    older = tmp_path / "older"
    write(older / "vlq" / "run2_20261001T000000Z.jsonl", OPEN_VLQ)
    conf = with_older(older)
    assert SiteScan.read(places, "euroqexa", conf["euroqexa"]).scans == []
    assert len(SiteScan.read(places, "vlq", {**conf["vlq"], "older_records": [str(older)]}).scans) == 1
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, conf, max_order=1) == 0


def test_an_older_record_whose_site_cannot_be_told_still_blocks_a_start(tmp_path, places, clock):
    older = tmp_path / "older"
    write(older / "run1_20261001T000000Z.jsonl", OPEN_UNKNOWN)
    with pytest.raises(runner.Refused, match="open or lost"):
        send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, with_older(older), max_order=1)


def test_a_record_in_folders_listed_twice_counts_once_in_the_budget(tmp_path, places, clock):
    older = tmp_path / "older"
    write(older / "eqe" / "run7_20260101T000000Z.jsonl", EQE_600)
    conf = with_older(older, older / "eqe", older)
    assert len(SiteScan.read(places, "euroqexa", conf["euroqexa"]).scans) == 1
    site = FakeSite()
    assert send(write_manifest(tmp_path / "m"), site, places, clock, conf, max_order=1) == 0   # 600 + 100 <= 1000
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 1)]
