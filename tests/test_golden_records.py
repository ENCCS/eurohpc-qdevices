"""Golden records of the runner: the whole text of each record, every line and every key in its order."""

import pytest
from fakes import QASM, STATE, FakeSite, eqe, records_of, write_manifest
from fakes.piastq import Broker, piastq_manifest
from fakes.vlq import make_vlq
from runner_calls import RULES_A, RULES_B, Calls

PAIRS = [(0, 1), (1, 2), (2, 3), (3, 4)]                     # the coupled pairs of the fake machine M1, 5 qubits
CUT = '{"event": "submitted", "order": 1, "name": "J1", "id": "J-47'      # a line cut inside its job id
CREATED = [("created", {"job": 7})]                           # the step lines of a VLQ-shaped job before Ctrl-C
UPLOADED = [*CREATED, ("uploaded", {"job": 7})]


def three_orders_with_rules(calls, tmp_path, monkeypatch) -> None:
    """Three orders with rules_a.py: a note of the check, a user verdict with a note and a key of its own, a skip."""
    site = FakeSite()
    site.notes = lambda job, read: [f"{job['name']} is noted"] if job["order"] == 2 else []
    user = {"before_job": lambda job, state: {"rule": "mine", "passed": True, "note": f"{job['name']} is seen",
                                              "angle": 0.5},
            "after_result": lambda job, result, state: {"rule": "skipper", "passed": True,
                                                        "skip": [3] if job["order"] == 2 else []}}
    calls.send(write_manifest(tmp_path / "m"), site, max_order=3, user_rules=user, rules_file=RULES_A)


def collect_only_resume(calls, tmp_path, monkeypatch) -> None:
    """The record of three_orders_with_rules with a line cut inside a job id, then a collect with rules_b.py."""
    three_orders_with_rules(calls, tmp_path, monkeypatch)
    rec = records_of(calls.places)[0]
    with open(rec, "a", encoding="utf-8") as fh:
        fh.write(CUT)
    calls.send(tmp_path / "m" / "manifest.json", FakeSite(), resume=rec, rules_file=RULES_B)


def refusal_at_order_1(calls, tmp_path, monkeypatch) -> None:
    """HTTP 400 to the job request of order 1: a refusal, final, at which the generic rule stop_on_refusal stops."""
    calls.send(write_manifest(tmp_path / "m"), FakeSite(submits={1: ("refuse", 400)}), max_order=3)


def failed_job_with_logs(calls, tmp_path, monkeypatch) -> None:
    """A job that ends FAILED: its logs, which hold the token, go to the record through the token filter."""
    calls.send(write_manifest(tmp_path / "m"), FakeSite(states={"J-1": [STATE("FAILED", final=True)]}), max_order=1)


def vlq_steps_then_resumed(calls, tmp_path, steps) -> None:
    """Ctrl-C in the job request of a VLQ-shaped order after these step lines, then a collect: Configuring."""
    m = write_manifest(tmp_path / "m", site="vlq")
    calls.send(m, FakeSite("vlq", seconds_left=3600, submits={1: ("steps", ("interrupt",), steps)}), max_order=1)
    configuring = FakeSite("vlq", seconds_left=3600, states={7: [STATE("Configuring", configuring=True)]})
    calls.send(m, configuring, resume=records_of(calls.places)[0])


def vlq_created_then_resumed(calls, tmp_path, monkeypatch) -> None:
    """Ctrl-C after "created": SubmitJob was never sent, so the collect makes the job final as not submitted."""
    vlq_steps_then_resumed(calls, tmp_path, CREATED)


def vlq_uploaded_then_resumed(calls, tmp_path, monkeypatch) -> None:
    """Ctrl-C after "uploaded": SubmitJob may have reached the site, so the collect stops (submit_unknown)."""
    vlq_steps_then_resumed(calls, tmp_path, UPLOADED)


def euroqexa_portal(calls, tmp_path, monkeypatch) -> None:
    """One job over the fake portal: the read with its layout, the result with the time stamps of the site."""
    portal = eqe.site(eqe.Portal(5, PAIRS, []))
    calls.send(eqe.manifest(tmp_path / "m", QASM), portal, max_order=1)


def piastq_broker(calls, tmp_path, monkeypatch) -> None:
    """One task over the fake broker: the counts of its shots and the wall seconds of the result."""
    calls.send(piastq_manifest(tmp_path / "m"), Broker().site(), max_order=1)


def vlq_service(calls, tmp_path, monkeypatch) -> None:
    """Order 1 of 2 over FakeVLQ: the read with the status file, the init lines, the step lines and the result."""
    _, clock, _, m, site = make_vlq(tmp_path)
    calls.send(m, site, clock=clock, max_order=1)


RECORDS = {case.__name__: case for case in (
    three_orders_with_rules, collect_only_resume, refusal_at_order_1, failed_job_with_logs, vlq_created_then_resumed,
    vlq_uploaded_then_resumed, euroqexa_portal, piastq_broker, vlq_service)}


@pytest.mark.parametrize("case", list(RECORDS))
def test_each_record_keeps_every_line_and_every_key_in_its_order(case, tmp_path, places, clock, monkeypatch, golden):
    RECORDS[case](Calls(places, clock), tmp_path, monkeypatch)
    [rec] = records_of(places)
    golden(f"record_{case}", rec.read_text(encoding="utf-8"))
