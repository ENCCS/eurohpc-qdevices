"""Answers of the wrong type and odd values end in the site's own kind of stop."""

import base64
import json
import math
import pickle

import httpx
import pytest
from fakes import TOKEN, FakeSite, cfg, eqe, lines_of, records_of, send, write_manifest
from fakes.piastq import Broker, run_broker
from fakes.vlq import go
from test_units_vlq import make
from vlq_fake import JobRecord

from qdevices import check
from qdevices.ledger import Ledger
from qdevices.resolve import resolve
from qdevices.sites import piastq
from qdevices.sites.vlq.results import ResultsFile


def portal(seen: list, **answers):
    """The fake portal, with its own answer to each path that ends with a key of `answers`."""
    fake = eqe.Portal(5, [(0, 1)], seen)

    def handler(request: httpx.Request) -> httpx.Response:
        for end, made in answers.items():
            if request.url.path.endswith(end):
                fake.keep(request)
                return made
        return fake(request)
    return handler


def stop_of(places) -> dict:
    return lines_of(records_of(places)[0])[-1]


@pytest.mark.parametrize("body", [["COMPLETED"], 7, "COMPLETED", True], ids=["list", "number", "text", "true"])
def test_a_state_read_of_the_wrong_type_is_a_status_error_and_the_order_stays_open(tmp_path, places, clock, body):
    code, lines = eqe.send(eqe.manifest(tmp_path / "m", eqe_text()), portal([], status=httpx.Response(200, json=body)),
                           places, clock, max_order=1)
    assert code == 1
    assert (lines[-1]["kind"], lines[-1]["error"]) == ("status_error", "the answer is not a JSON object")
    assert Ledger(lines).orders[1].status == "open"


def eqe_text() -> bytes:
    return b'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[1];\ncreg c[1];\nx q[0];\nmeasure q -> c;\n'


def test_a_piastq_state_of_the_wrong_type_is_a_status_error(tmp_path, places, clock):
    broker = Broker(states=[lambda: httpx.Response(200, json=[1])])
    assert run_broker(tmp_path, places, clock, broker) == 1
    assert (stop_of(places)["kind"], stop_of(places)["error"]) == ("status_error", "the answer is not a JSON object")


@pytest.mark.parametrize("result", [{"result": [[float("inf")]]}, {"result": [[[0]]]}], ids=["infinity", "a list"])
def test_a_piastq_shot_that_is_not_bits_is_a_result_error_and_the_order_stays_open(tmp_path, places, clock, result):
    broker = Broker(results=[lambda: httpx.Response(200, content=json.dumps(result).encode())])
    assert run_broker(tmp_path, places, clock, broker) == 1
    assert (stop_of(places)["kind"], stop_of(places)["error"]) == ("result_error",
                                                                    "a shot of the result is not a list of bits")


@pytest.mark.parametrize("answer", [
    lambda: httpx.Response(200, json=[1]),
    lambda: httpx.Response(200, json={"names": 5}),
], ids=["a list", "names a number"])
def test_check_live_of_a_piastq_read_of_the_wrong_type_fails_with_its_text(places, clock, answer):
    said: list[str] = []
    site = piastq.PiastQ(TOKEN, "M1", transport=httpx.MockTransport(lambda request: answer()))
    assert check.check("piastq", live=True, token=TOKEN, manifest_path=None, cfg=cfg(), places=places, clock=clock,
                       sleep=clock.sleep, host="h", make_site=lambda *a, **k: site, say=said.append) == 1
    assert said[-1].startswith("FAILED: the machine cannot be read: the answer ")


def test_check_live_of_a_euroqexa_resource_answered_with_a_list_fails_with_its_text(places, clock):
    said: list[str] = []
    site = eqe.site(portal([], **{"/resources/M1": httpx.Response(200, json=["M1"])}))
    assert check.check("euroqexa", live=True, token=TOKEN, manifest_path=None, cfg=cfg(), places=places, clock=clock,
                       sleep=clock.sleep, host="h", make_site=lambda *a, **k: site, say=said.append) == 1
    assert said[-1] == "FAILED: the machine cannot be read: the answer is not a JSON object"


def create_of(kind: str, answer):
    """A CreateJob answer for the job of one Q_COMMAND; None lets the fake answer the others."""
    def create(request: httpx.Request):
        env = {e["Name"]: e["Value"] for e in json.loads(request.content)["JobSpecification"]["EnvironmentVariables"]}
        return answer() if env["Q_COMMAND"] == kind else None
    return create


@pytest.mark.parametrize("body", [[1], 5, {"Id": 7, "Tasks": [5]}, {"Id": 7, "Tasks": {"a": 1}},
                                  {"Id": 7, "Tasks": [{"Name": "t"}]}, {"Id": [7], "Tasks": [{"Id": 1}]}],
                         ids=["a list", "a number", "a task that is a number", "tasks as an object",
                              "a task with no id", "an id that is a list"])
def test_a_vlq_create_job_answer_of_the_wrong_type_leaves_the_order_unknown_and_sends_nothing_twice(
        tmp_path, places, clock, body):
    fake, m, site = make(tmp_path, places, clock,
                         {"CreateJob": create_of("backend_run", lambda: httpx.Response(200, json=body))})
    assert go(m, site, places, clock, max_order=1) == 2
    stop = stop_of(places)
    assert stop["kind"] == "unknown" and stop["error"] in ("the answer is not a JSON object",
                                                           "the answer to CreateJob has no job with a task")
    assert len([r for r in fake.seen if r.url.path.endswith("SubmitJob")]) == 1     # the init job only
    assert Ledger(lines_of(records_of(places)[0])).orders[1].status == "lost"


def test_a_vlq_upload_answered_with_a_number_is_a_site_error(tmp_path, places, clock):
    _fake, m, site = make(tmp_path, places, clock,
                          {"UploadFilesToJobExecutionDir": lambda request: httpx.Response(200, json=5)})
    assert go(m, site, places, clock, max_order=1) == 1                 # at the upload of the init job's token
    assert stop_of(places)["kind"] == "prepare"


def test_a_vlq_download_that_is_not_base64_is_a_result_error(tmp_path, places, clock):
    def download(request: httpx.Request):
        return httpx.Response(200, json="abc") if b"/results.pkl" in request.content else None

    _fake, m, site = make(tmp_path, places, clock, {"DownloadFileFromCluster": download})
    assert go(m, site, places, clock, max_order=1) == 1
    assert (stop_of(places)["kind"], stop_of(places)["error"]) == (
        "result_error", "the download of results.pkl is not a text of base64 within the size limit")


@pytest.mark.parametrize("seconds", [10 ** 400, math.nan, math.inf, -1.0, "1.0"])
def test_vlq_device_seconds_that_are_not_finite_or_are_negative_are_not_taken(seconds):
    assert ResultsFile.device_seconds(pickle.dumps(JobRecord(seconds))) is None


@pytest.mark.parametrize("seconds", [0, 0.42, 10 ** 300])
def test_vlq_device_seconds_that_are_finite_and_not_negative_are_taken(seconds):
    assert ResultsFile.device_seconds(pickle.dumps(JobRecord(seconds))) == float(seconds)


@pytest.mark.parametrize("seconds", [10 ** 400, math.nan, -0.5], ids=["huge", "nan", "negative"])
def test_a_vlq_job_with_device_seconds_that_cannot_be_taken_keeps_its_result_with_no_seconds_in_standard_json(
        tmp_path, places, clock, seconds):
    def download(request: httpx.Request):
        if b"/job.pkl" not in request.content:
            return None
        return httpx.Response(200, json=base64.b64encode(pickle.dumps(JobRecord(seconds))).decode())

    _fake, m, site = make(tmp_path, places, clock, {"DownloadFileFromCluster": download})
    assert go(m, site, places, clock, max_order=1) in (0, 2)
    text = records_of(places)[0].read_text()
    assert "NaN" not in text and "Infinity" not in text
    result = next(line for line in lines_of(records_of(places)[0]) if line["event"] == "result")
    assert result["seconds"] is None


@pytest.mark.parametrize("uuid", ["u\n1", "u" * 70_000, "u/../1", "u?1"], ids=["newline", "too long", "dots", "query"])
def test_a_job_id_that_no_url_holds_leaves_the_order_lost_and_resolve_takes_it(tmp_path, places, clock, uuid):
    seen: list = []
    m = eqe.manifest(tmp_path / "m", eqe_text())
    code, lines = eqe.send(m, portal(seen, job=httpx.Response(200, json={"uuid": uuid})), places, clock, max_order=1)
    assert code == 2
    assert (lines[-1]["kind"], lines[-1]["error"]) == ("unknown", "the answer to the job request has no uuid that a "
                                                                  "URL can hold")
    assert "submitted" not in [line["event"] for line in lines] and len(eqe.posts(seen)) == 1
    rec = records_of(places)[0]
    assert Ledger(lines).orders[1].status == "lost"
    assert "has the job u-7" in resolve(rec, 1, "u-7", places=places, clock=clock, host="h")
    code, lines = eqe.send(m, portal(seen), places, clock, resume=rec)
    assert code == 0 and len(eqe.posts(seen)) == 1 and Ledger(lines).orders[1].status == "final"


def test_an_open_order_whose_id_no_url_holds_is_a_status_error_and_resolve_takes_it(tmp_path, places, clock):
    m = eqe.manifest(tmp_path / "m", eqe_text())
    code, _ = eqe.send(m, portal([], status=httpx.Response(503)), places, clock, max_order=1)
    rec = records_of(places)[0]
    text = rec.read_text().replace('"id": "u-1"', '"id": "u\\n1"')        # a record of the code before this fix
    rec.write_text(text)
    seen: list = []
    code, lines = eqe.send(m, portal(seen), places, clock, resume=rec)
    assert code == 1 and lines[-1]["kind"] == "status_error" and not eqe.posts(seen)
    assert lines[-1]["error"].startswith("the request cannot be made: Invalid non-printable ASCII character")
    assert resolve(rec, 1, None, places=places, clock=clock, host="h") == (
        "order 1 is final: the site gave a job id that no URL can hold, so a job may exist; it is not cancelled, and "
        "it counts at the job time limit")
    order = Ledger(lines_of(rec)).orders[1]
    assert (order.final, order.budget(100.0)) == ("resolved_stuck", 100.0)


class Loud:
    """A verdict value whose text ends the process."""

    def __str__(self) -> str:
        raise SystemExit(4)


def test_a_verdict_value_whose_text_raises_an_exit_is_a_failed_verdict(tmp_path, places, clock):
    user = {"before_job": lambda job, state: {"passed": True, "rule": "mine", "value": Loud()}}
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1, user_rules=user) == 2
    stop = stop_of(places)
    assert (stop["kind"], stop["rule"]) == ("rule", "before_job")
    assert stop["reason"] == "rule before_job: the hook before_job raised SystemExit: 4"


def test_a_euroqexa_result_field_nested_too_deep_is_a_result_error(tmp_path, places, clock):
    nested = json.dumps({"result": "[" * 100_000 + "]" * 100_000})
    code, lines = eqe.send(eqe.manifest(tmp_path / "m", eqe_text()),
                           portal([], result=httpx.Response(200, content=nested.encode())), places, clock, max_order=1)
    assert code == 1 and (lines[-1]["kind"], lines[-1]["error"]) == ("result_error", "the result field is not JSON")


def test_a_vlq_download_that_is_not_ascii_is_a_result_error(tmp_path, places, clock):
    def download(request: httpx.Request):
        return httpx.Response(200, json="é") if b"/results.pkl" in request.content else None

    _fake, m, site = make(tmp_path, places, clock, {"DownloadFileFromCluster": download})
    assert go(m, site, places, clock, max_order=1) == 1 and stop_of(places)["kind"] == "result_error"


def test_a_set_of_numbers_is_read_in_the_order_of_the_numbers():
    from qdevices.sites import euroqexa
    assert euroqexa._plain({10, 2}) == [2, 10] and euroqexa._plain({(1, 10), (1, 2)}) == [[1, 2], [1, 10]]
