"""Golden stops of the runner: each kind of stop, its exit code and its last line as on disk, keys in order."""

import json

import pytest
from fakes import QASM, STATE, FakeSite, lines_of, records_of, write_manifest
from runner_calls import Calls, ctrl_c

from qdevices import record
from qdevices.resolve import resolve
from qdevices.sites.base import Expired, NoAnswer, SiteError

WITH_RULE_LINES = {"rule_before_call"}        # also pin the rule lines: "order": null, as in the stop


def fail_write_once(monkeypatch, failing: str) -> None:
    """Record.write raises OSError once, at the first line of the event `failing`, before anything of it is written."""
    write, hit = record.Record.write, []

    def once(self, event, **fields):
        if event == failing and not hit:
            hit.append(event)
            raise OSError(28, "No space left on device")
        return write(self, event, **fields)

    monkeypatch.setattr(record.Record, "write", once)


def sends(calls, tmp_path, fake, **manifest) -> None:
    """One call that sends order 1 of the manifest in tmp_path / "m": three orders, unless `manifest` gives others."""
    calls.send(write_manifest(tmp_path / "m", **manifest), fake, max_order=1)


def read(calls, tmp_path, monkeypatch) -> None:
    """The read of the machine before the first job gets HTTP 503."""
    site = FakeSite()

    def busy():
        raise SiteError("HTTP 503 to GET resources/M1", status=503, body="busy", step="read")

    site.read = busy
    sends(calls, tmp_path, site)


def check_problems(calls, tmp_path, monkeypatch) -> None:
    """The check of each job against the read of the call finds a problem."""
    sends(calls, tmp_path, FakeSite(problems=["the text has more qubits than the machine"]))


def check_changed_file(calls, tmp_path, monkeypatch) -> None:
    """The file of order 1 changes on disk after the manifest was read (here, in the read of the machine)."""
    site = FakeSite()
    plain = site.read

    def read_and_change():
        (tmp_path / "m" / "J1.qasm").write_bytes(QASM + b"// changed\n")
        return plain()

    site.read = read_and_change
    sends(calls, tmp_path, site)


def prepare(calls, tmp_path, monkeypatch) -> None:
    """The init job of a VLQ-shaped order cannot be made (HTTP 500 to CreateJob): no metered job is made."""
    site = FakeSite("vlq", seconds_left=3600)

    def init_fails(job, note):
        note("init_submitting")
        raise SiteError("HTTP 500 to POST /JobManagement/CreateJob", status=500, body="no", step="init_create")

    site.prepare = init_fails
    sends(calls, tmp_path, site, site="vlq")


def lost(calls, tmp_path, monkeypatch) -> None:
    """Ctrl-C in the job request leaves order 1 lost; a collect stops at it."""
    sends(calls, tmp_path, FakeSite(submits={1: ("interrupt",)}))
    calls.send(tmp_path / "m" / "manifest.json", FakeSite(), resume=records_of(calls.places)[0])


def submit_unknown(calls, tmp_path, monkeypatch) -> None:
    """A lost VLQ-shaped order that resolve gives the job 7, with no "created" line: Configuring at the collect."""
    sends(calls, tmp_path, FakeSite("vlq", seconds_left=3600, submits={1: ("noanswer",)}), site="vlq")
    rec = records_of(calls.places)[0]
    resolve(rec, 1, "7", places=calls.places, clock=calls.clock, host="host-a")
    configuring = FakeSite("vlq", seconds_left=3600, states={7: [STATE("Configuring", configuring=True)]})
    calls.send(tmp_path / "m" / "manifest.json", configuring, resume=rec)


def status_error(calls, tmp_path, monkeypatch) -> None:
    """Two reads of the state get no answer, the third gets HTTP 403: the order stays open."""
    silent = NoAnswer("no answer to GET status: ConnectError", step="status")
    forbidden = SiteError("HTTP 403 to GET status", status=403, step="status")
    sends(calls, tmp_path, FakeSite(states={"J-1": [silent, silent, forbidden]}))


def result_error(calls, tmp_path, monkeypatch) -> None:
    """The job is finished and its result cannot be read, as the answer is not JSON: the order stays open."""
    site = FakeSite()

    def not_json(job_id):
        raise SiteError("the answer is not JSON", status=200, body="{counts", step="result")

    site.result = not_json
    sends(calls, tmp_path, site)


def result_expired_at_status(calls, tmp_path, monkeypatch) -> None:
    """The site answers a read of the state that it does not know the job any more."""
    gone = Expired("HTTP 404 to GET status: the site does not know the job", status=404, step="status")
    sends(calls, tmp_path, FakeSite(states={"J-1": [gone]}))


def result_expired_at_result(calls, tmp_path, monkeypatch) -> None:
    """The job is finished, and the site answers the read of its result that it does not know the job."""
    site = FakeSite()

    def gone(job_id):
        raise Expired("HTTP 404 to GET result: the site does not know the job", status=404, step="result")

    site.result = gone
    sends(calls, tmp_path, site)


def rule_failed(calls, tmp_path, monkeypatch) -> None:
    """A generic rule is not met before the job: 300 shots at a site whose limit is 200."""
    sends(calls, tmp_path, FakeSite(max_shots=200), jobs=(("J1", 300),))


def rule_skip_of_a_sent_order(calls, tmp_path, monkeypatch) -> None:
    """A user rule after the result of order 1 names order 1, which was sent, to skip."""
    user = {"after_result": lambda job, result, state: {"rule": "skipper", "passed": True, "skip": [1]}}
    calls.send(write_manifest(tmp_path / "m"), FakeSite(), max_order=3, user_rules=user)


def rule_before_call(calls, tmp_path, monkeypatch) -> None:
    """The machine is not online: the generic rule machine stops the call at before_call, before any job."""
    sends(calls, tmp_path, FakeSite(read={"machine": "M1", "online": False}))


def timeout(calls, tmp_path, monkeypatch) -> None:
    """The job is still RUNNING at wait_seconds: it is not cancelled, and the order stays open."""
    sends(calls, tmp_path, FakeSite(states={"J-1": [STATE()]}))


def unknown_503(calls, tmp_path, monkeypatch) -> None:
    """HTTP 503 with a body to the job request: it is not known whether a job runs."""
    sends(calls, tmp_path, FakeSite(submits={1: ("unknown", 503, "busy")}))


def unknown_no_answer(calls, tmp_path, monkeypatch) -> None:
    """No answer to the job request."""
    sends(calls, tmp_path, FakeSite(submits={1: ("noanswer",)}))


def unknown_no_id(calls, tmp_path, monkeypatch) -> None:
    """An answer to the job request that has no job id."""
    sends(calls, tmp_path, FakeSite(submits={1: ("noid",)}))


def error(calls, tmp_path, monkeypatch) -> None:
    """A RuntimeError in the job request: an error of the program."""
    sends(calls, tmp_path, FakeSite(submits={1: ("crash",)}))


def interrupt_in_prepare(calls, tmp_path, monkeypatch) -> None:
    """Ctrl-C in the work before a VLQ-shaped job, once its init job 5 is made."""
    site = FakeSite("vlq", seconds_left=3600)

    def init_made_then_ctrl_c(job, note):
        note("init_submitting")
        note("init_created", init_job=5)
        raise KeyboardInterrupt()

    site.prepare = init_made_then_ctrl_c
    sends(calls, tmp_path, site, site="vlq")


def interrupt_in_submit(calls, tmp_path, monkeypatch) -> None:
    """Ctrl-C in the job request of a VLQ-shaped order, once its job 7 is made ("created")."""
    steps = ("steps", ("interrupt",), [("created", {"job": 7})])
    sends(calls, tmp_path, FakeSite("vlq", seconds_left=3600, submits={1: steps}), site="vlq")


def interrupt_in_wait(calls, tmp_path, monkeypatch) -> None:
    """Ctrl-C in the wait for the job J-1."""
    sends(calls, tmp_path, FakeSite(states={"J-1": [ctrl_c]}))


def write_failed_result(calls, tmp_path, monkeypatch) -> None:
    """The result line of the job J-1 cannot be written (OSError): an error of the program."""
    fail_write_once(monkeypatch, "result")
    sends(calls, tmp_path, FakeSite())


def write_failed_failed(calls, tmp_path, monkeypatch) -> None:
    """The failed line of the job J-1, which ended FAILED, cannot be written (OSError): an error of the program."""
    fail_write_once(monkeypatch, "failed")
    sends(calls, tmp_path, FakeSite(states={"J-1": [STATE("FAILED", final=True)]}))


STOPS = {case.__name__: case for case in (
    read, check_problems, check_changed_file, prepare, lost, submit_unknown, status_error, result_error,
    result_expired_at_status, result_expired_at_result, rule_failed, rule_skip_of_a_sent_order, rule_before_call,
    timeout, unknown_503, unknown_no_answer, unknown_no_id, error, interrupt_in_prepare, interrupt_in_submit,
    interrupt_in_wait, write_failed_result, write_failed_failed)}


@pytest.mark.parametrize("case", list(STOPS))
def test_each_stop_keeps_its_exit_code_and_its_last_line(case, tmp_path, places, clock, monkeypatch, golden):
    calls = Calls(places, clock)
    STOPS[case](calls, tmp_path, monkeypatch)
    [rec] = records_of(places)
    rows = rec.read_text(encoding="utf-8").splitlines()
    rules = [row for row in rows if json.loads(row)["event"] == "rule"] if case in WITH_RULE_LINES else []
    golden(f"stops_{case}", "\n".join([calls.exits(), *rules, rows[-1]]) + "\n")


@pytest.mark.parametrize("case, event", [("write_failed_result", "result"), ("write_failed_failed", "failed")])
def test_a_final_line_that_cannot_be_written_leaves_a_stop_line_that_names_the_job(case, event, tmp_path, places,
                                                                                     clock, monkeypatch):
    calls = Calls(places, clock)
    STOPS[case](calls, tmp_path, monkeypatch)
    lines = lines_of(records_of(places)[0])
    assert calls.codes == [3]
    assert not [line for line in lines if line["event"] == event]
    stop = lines[-1]
    assert (stop["event"], stop["kind"], stop["order"], stop["id"]) == ("stop", "error", 1, "J-1")
