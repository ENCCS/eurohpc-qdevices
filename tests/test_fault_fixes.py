"""The third round of fault fixes, items 4 to 10: each fault is a refusal, a stop or a line, before anything is sent."""

import copy
import json

import httpx
import pytest
from fakes import FakeClock, FakeSite, cfg, eqe, lines_of, places_in, records_of, send, write_manifest
from fakes.vlq import _CLUSTERS, creates
from test_site_answers import eqe_text, portal
from test_units_vlq import make

from qdevices import config, rules, runner
from qdevices.dryrun import dry_run
from qdevices.qasm import Qasm
from qdevices.qasm.statement import NESTING
from qdevices.resolve import resolve
from qdevices.sites import piastq
from qdevices.sites.base import Channel, SiteError, http_client
from qdevices.sites.euroqexa import EuroQExa
from qdevices.values import in_url


@pytest.mark.parametrize("walltime", ["7200", 7200.0, True, [7200]])
def test_a_max_walltime_of_the_wrong_type_stops_at_the_read_before_any_init_job(tmp_path, places, clock, walltime):
    clusters = copy.deepcopy(_CLUSTERS)
    clusters[0]["NodeTypes"][0]["MaxWalltime"] = walltime
    answers = {"ListAvailableClusters": lambda request: httpx.Response(200, json=clusters)}
    fake, m, site = make(tmp_path, places, clock, answers)
    assert send(m, site, places, clock, max_order=1) == 1
    lines = lines_of(records_of(places)[0])
    assert (lines[-1]["event"], lines[-1]["kind"]) == ("stop", "read")
    assert "MaxWalltime" in lines[-1]["reason"] and not creates(fake)
    assert not {"init", "submitting"} & {line["event"] for line in lines}


@pytest.mark.parametrize("guard", ["if (c == 1) ", "if (c[0]) if (c[0] == 1) ", "if(c==1)"])
def test_a_gate_under_a_condition_is_among_the_gate_names(guard):
    text = f"OPENQASM 2.0;\nqreg q[2];\ncreg c[2];\n{guard}h q[0];\nx q[1];\n"
    assert Qasm.parse(text).gate_names == {"h", "x"}


def test_a_gate_under_more_conditions_than_are_read_is_not_named_as_statement_parse_reads_none():
    deep = "if (c) " * (NESTING + 1)
    assert Qasm.parse(f"qreg q[1];\n{'if (c) ' * NESTING}h q[0];\n").gate_names == {"h"}
    assert Qasm.parse(f"qreg q[1];\n{deep}h q[0];\n").gate_names == set()


LIMITS = {"max_shots": "vlq", "site_max_shots": "piastq"}


@pytest.mark.parametrize("value", ["0", "-5", "0.5"])
@pytest.mark.parametrize("key", list(LIMITS))
def test_a_limit_below_1_in_the_config_is_refused(key, value):
    if key.endswith("shots") and value == "0.5":
        value = "-1"                  # a float is the wrong type for these
    with pytest.raises(config.ConfigError) as refused:
        config.parse(f"[{LIMITS[key]}]\n{key} = {value}\n")
    assert str(refused.value) == f"[{LIMITS[key]}] {key} must be 1 or more"


def test_a_job_limit_may_be_a_fraction_and_must_be_above_0():
    assert config.parse("[vlq]\njob_seconds_limit = 0.5\n")["vlq"]["job_seconds_limit"] == 0.5
    with pytest.raises(config.ConfigError) as refused:
        config.parse("[vlq]\njob_seconds_limit = 0\n")
    assert str(refused.value) == "[vlq] job_seconds_limit must be above 0"


def test_a_budget_of_0_stops_every_send_and_leaves_the_config_good_and_a_negative_one_is_refused():
    assert config.parse("[vlq]\nbudget_seconds = 0\n")["vlq"]["budget_seconds"] == 0
    state = {"used_seconds": 0.0, "budget_seconds": 0, "job_seconds_limit": 1.0}
    assert rules.budget({"shots": 1}, state)["passed"] is False
    with pytest.raises(config.ConfigError) as refused:
        config.parse("[vlq]\nbudget_seconds = -1\n")
    assert str(refused.value) == "[vlq] budget_seconds must be 0 or more"


def test_a_piastq_answer_nested_too_deep_is_not_the_busy_answer():
    assert piastq.site._busy("[" * 200000) is False


def test_the_notes_of_a_job_with_no_no_modify_read_no_text():
    assert EuroQExa.notes({"options": {}}, {"name": "M1"}) == []


def test_a_shot_limit_of_0_is_a_limit_not_none_in_the_rule_and_the_dry_run(tmp_path):
    assert rules.shot_limit({"shots": 10}, {"site_max_shots": None, "max_shots": 0})["passed"] is False
    conf = cfg()
    conf["euroqexa"]["max_shots"] = 0
    said: list[str] = []
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert dry_run(m, cfg=conf, places=places_in(tmp_path), clock=FakeClock(), say=said.append) == 1
    assert "  FAILED: order 1 (J1): 10 shots, the limit is 0" in said


def test_a_lone_surrogate_is_an_id_no_url_holds_and_a_request_that_cannot_be_made(tmp_path, places, clock):
    assert in_url("u\ud800") is False
    sent: list = []
    channel = Channel(http_client("https://site", {}, timeout=1, transport=httpx.MockTransport(sent.append)))
    with pytest.raises(SiteError, match="the request cannot be made"):
        channel.request("GET", "/jobs/u\ud800", step="status")
    assert sent == []
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, FakeSite(submits={1: ("noanswer",)}), places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    with pytest.raises(runner.Refused, match="cannot be put in a URL"):
        resolve(rec, 1, "u\ud800", places=places, clock=clock, host="h")


NESTED = "[" * 2000 + "]" * 2000          # parsed by json, deeper than the code after it can recurse


@pytest.mark.parametrize("body", [f'{{"result": {NESTED}}}', json.dumps({"result": NESTED})], ids=["value", "text"])
def test_a_result_nested_too_deep_is_a_result_that_cannot_be_read(tmp_path, places, clock, body):
    m = eqe.manifest(tmp_path / "m", eqe_text())
    code, lines = eqe.send(m, portal([], result=httpx.Response(200, text=body)), places, clock, max_order=1)
    assert (code, lines[-1]["event"], lines[-1]["kind"]) == (1, "stop", "result_error")


def test_an_answer_deeper_than_the_limit_is_not_read():
    channel = Channel(http_client("https://site", {}, timeout=1,
                                  transport=httpx.MockTransport(lambda r: httpx.Response(200, text=NESTED))))
    with pytest.raises(SiteError, match="the answer is not JSON of at most 200 levels"):
        channel.answer("GET", "/x", step="status")


@pytest.mark.parametrize(("text", "refusal"), [("bad gateway", False), ("invalid qubit_index", True),
                                               ("cz_gate locus", True),
                                               ("unknown gate rx", True), ("the gates are not native", True),
                                               ("qubits 3 and 4 are not a pair", True), ("no couplers", True)])
def test_a_refusal_word_of_euroqexa_starts_a_word_and_a_gateway_is_none(text, refusal):
    assert bool(EuroQExa.refusal.body(text)) is refusal
