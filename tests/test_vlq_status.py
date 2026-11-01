"""The public status file of VLQ: read once a call with no token, kept in the read, and the rule site_status."""

import json

import httpx
import pytest
from fakes import cfg, lines_of, records_of
from fakes.vlq import STATUS_UP, TOKEN, creates, go, make_vlq

from qdevices import check, rules
from qdevices.sites.vlq import STATUS
from qdevices.sites.vlq.wire import STATUS_ROWS

UP = {"flags": dict.fromkeys(STATUS_ROWS, True), "timestamp": STATUS_UP["timestamp"], "error": None}


def first(lines: list[dict], event: str, **fields) -> dict:
    return next(e for e in lines if e["event"] == event and all(e.get(k) == v for k, v in fields.items()))


def status_headers(fake) -> list[dict]:
    return [headers for path, headers in fake.headers if path == "/vlq-status.json"]


def test_with_every_flag_up_the_call_goes_and_the_read_line_keeps_the_flags(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path)
    said = []
    assert go(m, site, places, clock, max_order=2, say=said.append) == 0
    lines = lines_of(records_of(places)[0])
    assert STATUS in first(lines, "start")["addresses"]
    assert first(lines, "read")["read"]["status"] == UP
    rule = first(lines, "rule", rule="site_status")
    assert rule["passed"] is True and rule["point"] == "before_call" and "note" not in rule
    assert "  rule site_status: pass" in said and not [s for s in said if "NOTE: the VLQ status file" in s]
    assert len(status_headers(fake)) == 1                       # once a call, for two jobs
    assert len([e for e in lines if e["event"] == "result"]) == 2


def test_no_token_goes_to_the_status_file(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path)
    assert go(m, site, places, clock, max_order=1) == 0
    sent = status_headers(fake)
    assert sent and all("authorization" not in headers and TOKEN not in str(headers) for headers in sent)
    heappe = [headers for path, headers in fake.headers if path.endswith("CreateJob")]
    assert heappe and all(headers["authorization"] == f"Bearer {TOKEN}" for headers in heappe)


@pytest.mark.parametrize("flag, row", list(STATUS_ROWS.items()))
def test_a_flag_that_is_false_stops_the_call_before_its_first_job(tmp_path, flag, row):
    places, clock, fake, m, site = make_vlq(tmp_path, status_file={**STATUS_UP, flag: False})
    assert go(m, site, places, clock, max_order=1) == 2
    lines = lines_of(records_of(places)[0])
    stop = lines[-1]
    assert stop["event"] == "stop" and stop["kind"] == "rule" and stop["rule"] == "site_status"
    assert stop["reason"] == f"rule site_status: the VLQ status file shows {row} down"
    assert first(lines, "read")["read"]["status"]["flags"][flag] is False
    assert creates(fake) == [] and not [e for e in lines if e["event"] in ("init", "submitting", "step")]


def test_each_row_that_is_down_is_named(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path, status_file={**STATUS_UP, "QPU_status": False,
                                                                    "total_status": False})
    assert go(m, site, places, clock, max_order=1) == 2
    rule = first(lines_of(records_of(places)[0]), "rule", rule="site_status")
    assert rule["passed"] is False and rule["down"] == ["QPU", "Overall"]
    assert rule["reason"] == "the VLQ status file shows QPU and Overall down"
    assert creates(fake) == []


@pytest.mark.parametrize("answer, why", [
    (500, "HTTP 500 to GET vlq-status.json"),
    (httpx.ConnectError("refused"), "no answer to GET vlq-status.json: ConnectError"),
    (b"<html>not json</html>", "the answer is not JSON"),
    ([True, True], "the answer is not a JSON object"),
    (204, "HTTP 204 to GET vlq-status.json"),                     # a success that is not 200
    pytest.param(b"[" * 100_000 + b"]" * 100_000, "the answer is not JSON", id="too_deep")])   # RecursionError
def test_a_status_file_that_cannot_be_read_gives_a_note_and_the_call_goes(tmp_path, answer, why):
    places, clock, _fake, m, site = make_vlq(tmp_path, status_file=answer)
    said = []
    assert go(m, site, places, clock, max_order=1, say=said.append) == 0
    lines = lines_of(records_of(places)[0])
    assert first(lines, "read")["read"]["status"] == {"flags": None, "timestamp": None, "error": why}
    note = f"the VLQ status file could not be read: {why}"
    rule = first(lines, "rule", rule="site_status")
    assert rule["passed"] is True and rule["note"] == note
    assert said.index(f"  NOTE: {note}") == said.index("  rule site_status: pass") + 1
    assert [e for e in lines if e["event"] == "result"]


def test_a_flag_that_is_missing_or_not_true_or_false_gives_a_note_and_the_call_goes(tmp_path):
    answer = {"QPU_status": True, "QCCW_status": True, "queue_available": "UP"}
    places, clock, _fake, m, site = make_vlq(tmp_path, status_file=answer)
    said = []
    assert go(m, site, places, clock, max_order=1, say=said.append) == 0
    lines = lines_of(records_of(places)[0])
    assert first(lines, "read")["read"]["status"] == {"flags": {**answer, "total_status": None}, "timestamp": None,
                                                      "error": None}
    note = "the VLQ status file does not show Internal Scheduler and Overall as up or down"
    assert first(lines, "rule", rule="site_status")["note"] == note and f"  NOTE: {note}" in said
    assert [e for e in lines if e["event"] == "result"]


def test_the_rule_site_status_alone():
    passed = rules.verdict("site_status", True)
    assert rules.site_status({"machine": "M1", "online": True}) == passed      # another site: no status
    assert rules.site_status({"status": UP}) == passed
    flags = {**UP["flags"], "QCCW_status": False, "total_status": None}
    down = rules.site_status({"status": {**UP, "flags": flags}})
    assert down["passed"] is False and down["reason"] == "the VLQ status file shows QCCSW down"
    zero = rules.site_status({"status": {**UP, "flags": {**UP["flags"], "queue_available": 0}}})
    assert zero["passed"] is True and zero["note"] == ("the VLQ status file does not show Internal Scheduler as "
                                                       "up or down")
    unread = rules.site_status({"status": {"flags": None, "timestamp": None, "error": "no answer"}})
    assert unread["passed"] is True and unread["note"] == "the VLQ status file could not be read: no answer"
    assert rules.site_status in rules.GENERIC["before_call"]


def test_check_live_stores_the_status_in_the_read_and_prints_it(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path, status_file={**STATUS_UP, "QPU_status": False})
    out = []
    assert check.check("vlq", live=True, token=TOKEN, manifest_path=m, cfg=cfg(), places=places, clock=clock,
                       sleep=clock.sleep, host="h", make_site=lambda *a, **k: site, say=out.append) == 0
    saved = json.loads(next((places.reads / "vlq").glob("read_*.json")).read_text())
    assert saved["status"]["flags"]["QPU_status"] is False and saved["member"] is True
    assert [line for line in out if line.startswith("  status: ")]
    assert creates(fake) == [] and len(status_headers(fake)) == 1
