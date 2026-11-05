"""The real site classes over MockTransport.

Refusals by site, no retry and no redirect, no site data unpickled, and the fixed addresses of the token.
"""

import hashlib
import importlib
import json
import pickle
from pathlib import Path

import httpx
import pytest
from fakes import QASM, TOKEN, FakeClock, cfg, lines_of, places_in, records_of, write_manifest

from qdevices import config, runner
from qdevices.errors import Refused
from qdevices.sites import SITES, euroqexa, make_site, piastq, pickle_reader, vlq
from qdevices.sites.base import Channel, SiteError, UnsafeRequest, http_client

SRC = Path(__file__).resolve().parent.parent / "src" / "qdevices"
PIASTQ_FILE = json.dumps({"number_of_qubits": 2, "quantum_circuit": [
    {"operation": "RXX", "qubits": [0, 1], "theta": 0.5}, {"operation": "MEASURE"}]}).encode()
# Each module that defines a site address or path, before its importers: a package reload runs only __init__.
RELOADED = ("euroqexa", "piastq.site", "piastq", "vlq.wire", "vlq.status", "vlq.target", "vlq.heappe", "vlq.site",
            "vlq")


def eqe_service(submit_answer, seen):
    def handler(request):
        seen.append((request.method, str(request.url)))
        path = request.url.path
        if path.endswith("/resources/M1"):
            return httpx.Response(200, json={"name": "M1", "qubits": 5, "online": True,
                                             "instructions": "[('r', {}), ('cz', {})]"})
        if path.endswith("num_pending_jobs"):
            return httpx.Response(200, json={"num_pending_jobs": 0})
        if path.endswith("/v1/job"):
            return submit_answer()
        if path.endswith("/status"):
            return httpx.Response(200, json={"status": "COMPLETED"})
        if path.endswith("/result"):
            return httpx.Response(200, json={"result": json.dumps({"1": 10}),
                                             "timestamp_scheduled": "2026-01-05 12:00:00.000000",
                                             "timestamp_completed": "2026-01-05 12:00:02.500000"})
        return httpx.Response(404)
    return handler


def run_eqe(tmp_path, submit_answer):
    places, clock, seen = places_in(tmp_path), FakeClock(), []
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10)))
    site = euroqexa.EuroQExa(TOKEN, "M1", transport=httpx.MockTransport(eqe_service(submit_answer, seen)))
    code = runner.send(m, site, cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="h",
                       say=lambda *a, **k: None, max_order=2)
    return code, seen, lines_of(records_of(places)[0])


def test_euroqexa_end_to_end(tmp_path):
    code, _seen, lines = run_eqe(tmp_path, lambda: httpx.Response(200, json={"uuid": "u-1"}))
    assert code == 0
    results = [e for e in lines if e["event"] == "result"]
    assert results[0]["counts"] == {"1": 10} and results[0]["seconds"] == 2.5


def test_a_307_to_a_submit_makes_one_request_and_an_unknown_order(tmp_path):
    answer = lambda: httpx.Response(307, headers={"Location": "https://elsewhere.invalid/v1/job"})  # noqa: E731
    code, seen, lines = run_eqe(tmp_path, answer)
    assert code == 2 and lines[-1]["kind"] == "unknown"
    assert len([s for s in seen if s[0] == "POST"]) == 1
    assert not [s for s in seen if "elsewhere" in s[1]]


def test_a_503_to_a_submit_makes_one_request_and_an_unknown_order(tmp_path):
    code, seen, lines = run_eqe(tmp_path, lambda: httpx.Response(503, text="busy"))
    assert code == 2 and lines[-1]["kind"] == "unknown" and lines[-1]["http_status"] == 503
    assert len([s for s in seen if s[0] == "POST"]) == 1


def test_an_answer_with_no_uuid_is_unknown(tmp_path):
    code, _seen, lines = run_eqe(tmp_path, lambda: httpx.Response(200, json={}))
    assert code == 2 and lines[-1]["kind"] == "unknown"


def test_a_euroqexa_refusal_names_a_word_of_the_site(tmp_path):
    code, _seen, lines = run_eqe(tmp_path, lambda: httpx.Response(422, text="the cz pair (3, 4) is not coupled"))
    assert code == 2 and [e for e in lines if e["event"] == "refused"]
    site = euroqexa.EuroQExa(TOKEN, "M1", transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    assert site.classify(SiteError("x", status=400, body="bad gate r", step="submit")) == "refused"
    assert site.classify(SiteError("x", status=400, body="bad request", step="submit")) == "unknown"
    assert site.classify(SiteError("x", status=500, body="gate", step="submit")) == "unknown"


def test_piastq_classes_and_the_busy_status(tmp_path):
    busy = json.dumps({"detail": json.dumps({"quantum_api_status_code": 429, "message": "max connections reached: 4"})})
    site = piastq.PiastQ(TOKEN, transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    out_of_range = '{"detail": "theta out of range"}'
    assert site.classify(SiteError("x", status=422, body=out_of_range, step="submit")) == "refused"
    assert site.classify(SiteError("x", status=422, body=busy, step="submit")) == "unknown"
    places, clock = places_in(tmp_path), FakeClock()
    answers = iter([httpx.Response(422, text=busy), httpx.Response(200, json={"status": "Completed"})])

    def handler(request):
        path = request.url.path
        if path.endswith("/machines"):
            return httpx.Response(200, json={"names": ["AQT"]})
        if path.endswith("/tasks"):
            return httpx.Response(200, json={"uid": "p-1"})
        if path.endswith("/status"):
            return next(answers)
        if path.endswith("/results"):
            return httpx.Response(200, json={"result": [[0, 0]] * 6 + [[1, 1]] * 4})
        return httpx.Response(404)

    folder = tmp_path / "m"
    folder.mkdir()
    (folder / "B.json").write_bytes(PIASTQ_FILE)
    (folder / "manifest.json").write_text(json.dumps({
        "format": "qdevices/1", "site": "piastq", "machine": "AQT", "project": "TEST-PROJECT",
        "jobs": [{"order": 1, "name": "B", "file": "B.json", "sha256": hashlib.sha256(PIASTQ_FILE).hexdigest(),
                  "shots": 10}]}))
    site = piastq.PiastQ(TOKEN, "AQT", transport=httpx.MockTransport(handler))
    code = runner.send(folder / "manifest.json", site, cfg=cfg(), places=places, clock=clock, sleep=clock.sleep,
                       host="h", say=lambda *a, **k: None, max_order=1)
    assert code == 0
    result = next(e for e in lines_of(records_of(places)[0]) if e["event"] == "result")
    assert result["counts"] == {"00": 6, "11": 4} and result["seconds_kind"] == "wall"


def test_piastq_has_the_limit_of_200_and_validate_holds_the_schema():
    job = {"text": PIASTQ_FILE, "shots": 201, "options": {}}
    assert piastq.PiastQ.max_shots == 200  # the generic shot rule applies it; the config may replace it
    assert piastq.PiastQ.validate(job, None) == []
    bad = json.dumps({"number_of_qubits": 2, "quantum_circuit": [{"operation": "RXX", "qubits": [0, 1], "theta": 0.7},
                                                                 {"operation": "MEASURE"}]}).encode()
    assert any("RXX" in p for p in piastq.PiastQ.validate({"text": bad, "shots": 10, "options": {}}, None))


def test_euroqexa_validate_with_no_modify_checks_the_gates_of_the_read():
    job = {"text": QASM, "shots": 10, "options": {"no_modify": True}}
    read = {"qubits": 5, "gate_names": ["r", "cz"]}
    assert any("not among the gates" in p for p in euroqexa.EuroQExa.validate(job, read))
    assert euroqexa.EuroQExa.validate({**job, "options": {}}, read) == []


def test_every_site_client_follows_no_redirect_and_has_no_retry():
    clock = FakeClock()
    for name in SITES:
        site = make_site(None, name, TOKEN, clock=clock, sleep=clock.sleep, site_config=config.parse("")[name])
        for client in site._clients:
            assert client.follow_redirects is False
            pool = getattr(client._transport, "_pool", None)
            assert pool is None or getattr(pool, "_retries", 0) == 0
        site.close()
    client = http_client("https://a.invalid", {}, timeout=1.0)
    assert client.follow_redirects is False and client._transport._pool._retries == 0


@pytest.mark.parametrize("method, path, keywords", [
    ("GET", "https://elsewhere.invalid/v1/job", {}), ("GET", "resources", {"follow_redirects": True}),
    ("GET", "resources", {"auth": ("user", "word")}), ("DELETE", "job/1", {}), ("delete", "job/1", {}),
    ("POST", "/JobManagement/CancelJob", {}), ("PUT", "tasks/1/Abort", {}), ("PATCH", "jobs/1/delete", {}),
    (b"DELETE", "job/1", {}), (b"GET", "job/1", {}), ("POST", "job/1/%63ancel", {}), ("POST", "job/1/%2563ANCEL", {}),
    ("POST", "job/1", {"params": {"action": "cancel"}}), ("PUT", "job/1", {"params": [("do", "Abort")]}),
    ("POST", "job/1?step=%64elete", {}), ("GET", "job/1", {"headers": {"Authorization": "Bearer OTHER"}}),
    ("POST", "tasks", {"headers": [("authorization", "")]})])
def test_a_request_that_could_leave_the_address_or_end_a_job_is_an_error_of_the_program(method, path, keywords):
    seen = []
    channel = Channel(http_client("https://fake.invalid", {}, timeout=1.0, transport=httpx.MockTransport(
        lambda request: seen.append(request) or httpx.Response(200, json={}))))
    with pytest.raises(UnsafeRequest, match="is never sent") as caught:
        channel.answer(method, path, step="submit", **keywords)
    assert seen == [] and not isinstance(caught.value, (SiteError, Refused))
    channel.request("GET", "job/1/cancel_reason", step="logs")        # why a job ended: a read, which goes
    assert [request.url.path for request in seen] == ["/job/1/cancel_reason"]


def test_an_unsafe_request_in_a_send_stops_the_call_with_exit_3_and_never_leaves(tmp_path, monkeypatch):
    def deletes(site, job, note, prepared=None):
        return site._http.answer("DELETE", "job/u-1", step="submit")

    monkeypatch.setattr(euroqexa.EuroQExa, "submit", deletes)
    code, seen, lines = run_eqe(tmp_path, lambda: httpx.Response(200, json={"uuid": "u-1"}))
    assert code == 3 and lines[-1]["kind"] == "error" and "UnsafeRequest" in lines[-1]["reason"]
    assert [method for method, _ in seen] == ["GET", "GET"]           # the read of the machine only


def test_no_other_http_client_is_made_in_the_package():
    for path in SRC.rglob("*.py"):
        text = path.read_text()
        if path.name != "base.py":
            assert "httpx.Client(" not in text and "httpx.get(" not in text and "httpx.post(" not in text, path


def test_no_flag_and_no_environment_variable_moves_an_address(monkeypatch):
    for name in ("MQSS_URL", "MQSS_PORT", "VLQ_HEAPPE", "VLQ_USERORG", "VLQ_STATUS", "PCSS_URL"):
        monkeypatch.setenv(name, "https://attacker.invalid")
    for name in RELOADED:
        importlib.reload(importlib.import_module(f"qdevices.sites.{name}"))
    assert euroqexa.ADDRESS == "https://portal.quantum.lrz.de:4000/v1"
    assert vlq.HEAPPE == "https://quantum.heappe.it4i.cz/heappe/heappe" and vlq.USERORG == "https://api.lexis.tech/userorg/api"
    assert vlq.STATUS == "https://quantum.heappe.it4i.cz/vlq-status.json" and vlq.VLQ.addresses[-1] == vlq.STATUS
    status = importlib.import_module("qdevices.sites.vlq.status")
    site = vlq.VLQ(TOKEN)
    status_file = status.StatusFile(site, vlq.VLQ.status_address)       # the folder of its client, and its file
    site.close()
    assert (status_file.folder, status_file.file) == ("https://quantum.heappe.it4i.cz", "vlq-status.json")
    assert piastq.ADDRESS == "https://api.quantum.psnc.pl/api/open"
    for path in (SRC / "sites").rglob("*.py"):
        assert "os.environ" not in path.read_text() and "getenv" not in path.read_text(), path
    for cls in SITES.values():
        assert all(a.startswith("https://") for a in cls.addresses)


def test_the_scan_reloads_each_module_that_names_an_address_or_sends_a_request():
    # A sender through a Channel names a request path. base.py names none and is not reloaded: others catch its errors.
    found = set()
    for path in (SRC / "sites").rglob("*.py"):
        text = path.read_text()
        if path.name != "base.py" and ('"https://' in text or ".request(" in text or ".answer(" in text):
            found.add(".".join(path.relative_to(SRC / "sites").with_suffix("").parts).removesuffix(".__init__"))
    assert found and found <= set(RELOADED), found - set(RELOADED)


def test_a_pickle_that_names_os_system_runs_nothing(tmp_path):
    marker = tmp_path / "ran"

    class Evil:
        def __reduce__(self):
            import os
            return (os.system, (f"touch {marker}",))

    data = pickle.dumps(Evil())
    out = pickle_reader.loads(data)
    assert not marker.exists()
    assert "stub" in repr(out)


def test_a_pickle_above_the_size_limit_is_refused(monkeypatch):
    monkeypatch.setattr(pickle_reader, "MAX_BYTES", 10)
    with pytest.raises(pickle_reader.PickleRefused, match="limit"):
        pickle_reader.loads(pickle.dumps(list(range(100))))
