"""Unit tables of the sites, on the real site classes over the fakes.

A file that cannot be sent, an answer nested too deep and a shot that is not a list of bits are each refused or a site
error, not an error of the program.
"""

import json

import httpx
import pytest
from fakes import QASM, TOKEN, cfg, eqe, records_of, send, write_manifest
from fakes.piastq import BUSY, EXPIRED, PAYLOAD, Broker
from fakes.vlq import FakeVLQ

from qdevices import sites
from qdevices.sites import piastq
from qdevices.sites.base import NoAnswer, Site, SiteError

MANIFEST = {"machine": "M1", "lexis_project": "TEST-LEXIS", "resource": "R1"}
FACTS = ("machine", "lexis_project", "resource_name", "wait_seconds")      # what make_site hands on to a site
MEASURE = {"operation": "MEASURE"}
NESTED = "[" * 100_000 + "]" * 100_000        # JSON nested deeper than the recursion limit of the parser


def through(fake, seen: list):
    """A handler that keeps the URL of each request, then lets the fake answer it."""
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return fake(request)
    return handler


def test_make_site_gives_the_class_of_each_name_with_its_machine_and_facts(clock, golden):
    rows = []
    for name in sites.SITES:
        for man in (None, MANIFEST):
            made = sites.make_site(man, name, TOKEN, clock=clock, sleep=clock.sleep, site_config=cfg()[name])
            assert type(made) is sites.SITES[name]
            facts = {key: getattr(made, key) for key in FACTS if hasattr(made, key)}
            rows.append(f"{name}, {'a manifest' if man else 'no manifest'}: {type(made).__name__} {facts}")
            made.close()
    vlq = sites.make_site(MANIFEST, "vlq", TOKEN, clock=clock, sleep=clock.sleep, site_config=cfg()["vlq"])
    assert vlq.clock is clock and vlq.sleep == clock.sleep
    vlq.close()
    golden("units_sites_make_site", "\n".join(rows) + "\n")


def test_make_site_passes_the_transport_to_each_client_that_a_read_uses(places, clock):
    for name, fake in (("euroqexa", eqe.Portal(5, [(0, 1)], [])), ("vlq", FakeVLQ(places)), ("piastq", Broker())):
        seen = []
        made = sites.make_site(MANIFEST, name, TOKEN, clock=clock, sleep=clock.sleep, site_config=cfg()[name],
                               transport=httpx.MockTransport(through(fake, seen)))
        made.read()
        made.close()
        addresses = type(made).addresses
        assert seen and all(url.startswith(addresses) for url in seen), name
        assert {a for a in addresses if any(url.startswith(a) for url in seen)} == set(addresses), name


@pytest.mark.parametrize("name, status, step, body, kind", [
    ("euroqexa", 400, "status", "gate", "unknown"),           # a word of a refusal, in an answer to a read
    ("euroqexa", 400, "submit", "gate", "refused"),
    ("piastq", 422, "status", "theta out of range", "unknown"),
    ("piastq", 422, "submit", "theta out of range", "refused"),
    ("vlq", 403, "upload:circuit_0000.qasm", None, "unknown"),  # a code that says nothing of the circuit
    ("vlq", 408, "upload:circuit_0000.qasm", None, "unknown"),
    ("vlq", 400, "upload:circuit_0000.qasm", None, "refused"),
])
def test_the_class_of_an_error_answer_by_its_step_and_its_code(clock, name, status, step, body, kind):
    made = sites.make_site(None, name, TOKEN, clock=clock, sleep=clock.sleep, site_config=cfg()[name])
    assert made.classify(SiteError(f"HTTP {status}", status=status, body=body, step=step)) == kind
    made.close()


ANSWERS_422 = {          # bodies of a 422 to the task request; each class is in the golden
    "the upstream 429 in a text": BUSY,
    "the upstream 429 in an object": json.dumps({"detail": {"quantum_api_status_code": 429}}),
    "a JSON list": json.dumps(["theta", "out of range"]),
    "a JSON text": json.dumps("busy"),
    "a detail that is a list": json.dumps({"detail": [{"msg": "theta out of range"}]}),
    "a detail that is not JSON": json.dumps({"detail": "theta out of range"}),
    "a text that is not JSON": "theta out of range",
    "an empty text": "",
    "no body": None,
    "a number, not a text": 5,
}


def test_the_class_of_each_answer_422_of_piastq_to_the_task_request(golden):
    made = piastq.PiastQ(TOKEN, transport=httpx.MockTransport(lambda request: httpx.Response(200)))
    rows = [f"{what}: {made.classify(SiteError('HTTP 422', status=422, body=body, step='submit'))}"
            for what, body in ANSWERS_422.items()]
    made.close()
    golden("units_sites_piastq_422", "\n".join(rows) + "\n")


@pytest.mark.parametrize("code", [404, 422, 500])
def test_a_piastq_machines_read_answered_with_the_body_of_an_expired_job_is_a_plain_site_error(code):
    made = piastq.PiastQ(TOKEN, "M1", transport=httpx.MockTransport(lambda request: httpx.Response(code, json=EXPIRED)))
    with pytest.raises(SiteError) as caught:
        made.read()
    made.close()
    error = caught.value
    assert type(error) is SiteError and (str(error), error.status, error.step, error.busy) == (
        f"HTTP {code} to GET /machines", code, "read", False)


def broker_file(*operations, qubits=2) -> bytes:
    """A file of a Piast-Q job with these operations."""
    return json.dumps({"number_of_qubits": qubits, "quantum_circuit": list(operations)}).encode()


SCHEMA = {               # a job file; its problems, in order, are in the golden
    "an operation that is not an object": broker_file(5, MEASURE),
    "a list as kind": broker_file({"operation": ["R"], "qubit": 0, "theta": 0.5, "phi": 0.5}, MEASURE),
    "two MEASUREs": broker_file(MEASURE, MEASURE),
    "RZ phi Infinity": broker_file({"operation": "RZ", "qubit": 0, "phi": float("inf")}, MEASURE),
    "RZ phi NaN": broker_file({"operation": "RZ", "qubit": 0, "phi": float("nan")}, MEASURE),
    "RZ on a qubit that is true": broker_file({"operation": "RZ", "qubit": True, "phi": 1}, MEASURE),
    "R with theta out of range": broker_file({"operation": "R", "qubit": 0, "theta": 1.5, "phi": 0}, MEASURE),
    "RXX on one qubit twice": broker_file({"operation": "RXX", "qubits": [1, 1], "theta": 0.25}, MEASURE),
    "MEASURE before an unknown operation": broker_file(MEASURE, {"operation": "H", "qubit": 0}),
    "no operation": broker_file(),
    "number_of_qubits 0": broker_file(MEASURE, qubits=0),
    "number_of_qubits true": broker_file(MEASURE, qubits=True),
    "a key of its own": json.dumps({"number_of_qubits": 1, "quantum_circuit": [MEASURE], "shots": 5}).encode(),
    "a list": b"[]",
    "a text that is not JSON": b"not json",
}


def test_the_schema_messages_of_piastq_and_their_order(golden):
    problems = {what: piastq.PiastQ.validate({"text": text, "shots": 10, "options": {}}, None)
                for what, text in SCHEMA.items()}
    assert problems["RZ phi Infinity"] == [NO_JSON]
    golden("units_sites_piastq_schema", "".join(f"{what}: {json.dumps(found)}\n" for what, found in problems.items()))


# case: (site, path end it answers, HTTP status, body, exit code, kind of the stop line)
STOPS = {
    "euroqexa_submit_503": ("euroqexa", "/v1/job", 503, {"text": "busy"}, 2, "unknown"),
    "piastq_submit_503": ("piastq", "/tasks", 503, {"text": "busy"}, 2, "unknown"),
    "euroqexa_status_not_json": ("euroqexa", "/status", 200, {"text": "not json"}, 1, "status_error"),
    "piastq_status_not_json": ("piastq", "/status", 200, {"text": "not json"}, 1, "status_error"),
    "piastq_submit_422_list": ("piastq", "/tasks", 422, {"json": ["theta", "out of range"]}, 2, "rule"),
    "piastq_shot_a": ("piastq", "/results", 200, {"json": {"result": [["a"]]}}, 1, "result_error"),
    "piastq_shot_none": ("piastq", "/results", 200, {"json": {"result": [[None]]}}, 1, "result_error"),
    "euroqexa_status_nested": ("euroqexa", "/status", 200, {"text": NESTED}, 1, "status_error"),
    "piastq_status_nested": ("piastq", "/status", 200, {"text": NESTED}, 1, "status_error"),
}
ERRORS = {               # error, http_status and step of the stop line at a site error
    "euroqexa_submit_503": ("HTTP 503 to POST job", 503, "submit"),
    "piastq_submit_503": ("HTTP 503 to POST /tasks", 503, "submit"),
    "euroqexa_status_not_json": ("the answer is not JSON", 200, "status"),
    "piastq_status_not_json": ("the answer is not JSON", 200, "status"),
    "piastq_shot_a": ("a shot of the result is not a list of bits", None, "result"),
    "piastq_shot_none": ("a shot of the result is not a list of bits", None, "result"),
    "euroqexa_status_nested": ("the answer is not JSON", 200, "status"),
    "piastq_status_nested": ("the answer is not JSON", 200, "status"),
}


def one_job(tmp_path, places, clock, name: str, end: str, answer, *, text: bytes | None = None,
            seen: list | None = None) -> int:
    """The exit code of a send of J1 over the fake of `name`, `answer()` answering each path that ends with `end`."""
    fake, plain = (eqe.Portal(5, [(0, 1)], []), QASM) if name == "euroqexa" else (Broker(), PAYLOAD)
    seen = [] if seen is None else seen

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, request.url.path))
        return answer() if request.url.path.endswith(end) else fake(request)

    made = (eqe.site(handler) if name == "euroqexa"
            else piastq.PiastQ(TOKEN, "M1", transport=httpx.MockTransport(handler)))
    m = write_manifest(tmp_path / "m", site=name, jobs=(("J1", 10),), text=plain if text is None else text)
    return send(m, made, places, clock, max_order=1)


@pytest.mark.parametrize("case", list(STOPS))
def test_the_record_from_the_job_request_on_at_an_answer_of_the_site(tmp_path, places, clock, golden, case):
    name, end, status, body, code, kind = STOPS[case]
    assert one_job(tmp_path, places, clock, name, end, lambda: httpx.Response(status, **body)) == code
    raw = records_of(places)[0].read_text().splitlines()
    lines = [json.loads(row) for row in raw]
    assert lines[-1]["event"] == "stop" and lines[-1]["kind"] == kind
    assert tuple(lines[-1].get(key) for key in ("error", "http_status", "step")) == ERRORS.get(case, (None,) * 3)
    # Only a 422 to the task request is a refusal: a "refused" line, then the stop of the rule.
    assert ("refused" in [line["event"] for line in lines]) == (case == "piastq_submit_422_list")
    start = next(i for i, line in enumerate(lines) if line["event"] == "submitting")
    golden(f"units_sites_stop_{case}", "\n".join(raw[start:]) + "\n")


NO_JSON = "the file holds NaN or Infinity, which a JSON request cannot carry"
# case: site, a file that cannot be sent as it is, and the problem the check finds in it
FILES = {
    "piastq_rz_phi_infinity": ("piastq", broker_file({"operation": "RZ", "qubit": 0, "phi": float("inf")}, MEASURE),
                               NO_JSON),                        # httpx encodes JSON with allow_nan=False
    "euroqexa_not_utf8": ("euroqexa", QASM + b"// \xff\n", "the file is not UTF-8 text"),   # submit decodes strictly
    "piastq_lone_surrogate": ("piastq", broker_file({"operation": "MEASURE", "note": "\ud800"}),
                              "the file holds a lone surrogate escape, which a JSON request cannot carry"),
}


@pytest.mark.parametrize("case", list(FILES))
def test_a_file_that_cannot_be_sent_is_refused_by_the_check_before_any_submitting_line(tmp_path, places, clock, case):
    name, text, problem = FILES[case]
    assert sites.SITES[name].validate({"text": text, "shots": 10, "options": {}}, None) == [problem]    # the dry run
    seen: list = []
    assert one_job(tmp_path, places, clock, name, "/none", lambda: httpx.Response(500), text=text, seen=seen) == 1
    lines = [json.loads(row) for row in records_of(places)[0].read_text().splitlines()]
    assert "submitting" not in [line["event"] for line in lines]
    stop = lines[-1]
    assert (stop["event"], stop["kind"], stop["problems"]) == ("stop", "check", [f"order 1 (J1): {problem}"])
    assert not [path for method, path in seen if method == "POST"]       # no job request was sent


STEPS = {                # the five steps of a site class, each in its simplest form
    "read": lambda self: {},
    "validate": staticmethod(lambda job, read: []),
    "submit": lambda self, job, note, prepared: "J-1",
    "status": lambda self, job_id: {"state": "COMPLETED", "final": True, "ok": True, "configuring": False},
    "result": lambda self, job_id: {"counts": {"1": 1}, "seconds": None},
}


@pytest.mark.parametrize("step", list(STEPS))
def test_a_site_class_that_lacks_a_step_fails_when_it_is_made(step):
    lacking = type("Lacking", (Site,), {name: form for name, form in STEPS.items() if name != step})
    with pytest.raises(TypeError, match=step):
        lacking(TOKEN)
    assert type("Whole", (Site,), dict(STEPS))(TOKEN).read() == {}


@pytest.mark.parametrize("error", [
    SiteError("HTTP 400", status=400, body="the cz pair (3, 4) is not coupled", step="submit"),
    SiteError("HTTP 422", status=422, body='{"detail": "theta out of range"}', step="submit"),
    SiteError("HTTP 400", status=400, step="upload:circuit_0000.qasm"),
    NoAnswer("no answer to POST job: ConnectError", step="submit"),
    ValueError("not an error of a site"),
])
def test_a_site_class_with_no_refusal_classifies_any_error_as_unknown(error):
    site = type("NoRefusal", (Site,), dict(STEPS))(TOKEN)
    assert site.refusal is None and site.classify(error) == "unknown"
