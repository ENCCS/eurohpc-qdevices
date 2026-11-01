"""What the readers of the ledger give where no golden or other test pins it, faults included."""

import json
from types import SimpleNamespace

import pytest
from fakes import FakeClock, FakeSite, lines_of, records_of, send, write_manifest
from fakes.older import write
from test_resolve_over_limit import WAITED, limits, over, waited

from qdevices import monitor, runner
from qdevices.ledger import Ledger
from qdevices.runner.call import Call
from qdevices.sites import SITES

SENT = {"event": "submitted", "order": 1, "name": "J1", "id": "J-1"}
RESULT = {"event": "result", "order": 1, "name": "J1", "id": "J-1", "shots": 10, "seconds": 2.5}
FAILED = {"event": "failed", "order": 1, "name": "J1", "id": "J-1"}
MADE = {"event": "step", "order": 1, "step": "created", "job": 5}     # the made step of FakeSite("vlq")
UPLOADED = {"event": "step", "order": 1, "step": "uploaded"}          # its submit step


def site(events):
    """The site of a record."""
    return Ledger(events).site


def project(events):
    """The project of a record."""
    return Ledger(events).project


def any_sent(events):
    """True when an order of a record was asked for or has a job id."""
    return Ledger(events).any_sent


def is_app(events):
    """True when the first start line of a record is one of this app."""
    return Ledger(events).is_app


def counted(events, order):
    """The seconds an order of a record counts with."""
    return Ledger(events).orders[order].counted_seconds


def tallied(path) -> tuple:
    """The results, shots, seconds, results with no seconds and counted seconds of the summary of a record."""
    s = monitor.summary(path)
    return s.results, s.shots, s.seconds, s.no_seconds, s.counted


def call_over(lines: list[dict], fake: FakeSite | None = None, *, prior: list[dict] | None = None) -> Call:
    """A Call whose record holds these lines after `prior`, on this fake site or on one with no made step."""
    return Call(man={"jobs": []}, site=fake or FakeSite(), site_config={}, rec=SimpleNamespace(lines=lines),
                prior=prior or [], clock=FakeClock(), sleep=None, say=None, user={})


def test_each_older_machine_of_the_registry_gives_its_site():
    machines = {machine: name for name in SITES for machine in SITES[name].profile.older_machines}
    assert machines == {"EQE1": "euroqexa", "VLQ": "vlq", "Piast-Q": "piastq"}
    assert {machine: site([{"machine": machine}]) for machine in machines} == machines


def test_a_site_on_any_line_wins_over_a_machine_on_an_earlier_line():
    assert site([{"machine": "EQE1"}, {"site": "piastq"}]) == "piastq"
    assert site([{"machine": "VLQ"}, {"machine": "EQE1"}]) == "vlq"


def test_a_site_not_in_the_registry_is_passed_over_and_then_a_machine_is_read():
    assert site([{"site": "not-a-site", "machine": "VLQ"}]) == "vlq"
    assert site([{"site": "not-a-site"}]) is None


def test_a_site_that_cannot_be_hashed_is_no_site_with_no_error():
    assert site([{"site": ["piastq"]}]) is None
    assert site([{"site": ["piastq"], "machine": "VLQ"}]) == "vlq"


def test_a_machine_that_cannot_be_hashed_names_no_site():
    assert site([{"machine": ["VLQ"]}]) is None
    assert site([{"machine": ["VLQ"]}, {"site": "vlq"}]) == "vlq"


def test_a_record_with_no_site_and_no_machine_has_no_site():
    assert site([{"event": "start"}]) is None
    assert site([]) is None


def test_a_project_on_a_later_line_wins_over_a_proposal_on_an_earlier_line():
    assert project([{"proposal": "P1"}, {"project": "P2"}]) == "P2"


def test_the_first_truthy_value_of_a_key_is_the_project_passing_over_an_empty_text_and_0():
    assert project([{"project": ""}, {"project": 0}, {"project": "P1"}, {"project": "P2"}]) == "P1"
    assert project([{"project": ""}, {"proposal": 0}, {"proposal": "P3"}]) == "P3"


def test_a_record_with_no_truthy_project_or_proposal_has_no_project():
    assert project([{"project": ""}, {"proposal": 0}]) is None
    assert project([]) is None


def test_nothing_is_sent_with_no_order_or_with_only_a_stop():
    assert any_sent([]) is False
    assert any_sent([{"event": "start"}, {"event": "submitting"}]) is False
    assert any_sent([{"event": "stop", "order": 1, "kind": "rule"}]) is False


def test_a_submitting_line_alone_a_step_with_an_id_and_a_submitted_line_with_an_id_of_0_or_no_id_are_sent():
    assert any_sent([{"event": "submitting", "order": 1}]) is True
    assert any_sent([MADE]) is True
    assert any_sent([{"event": "step", "order": 1, "step": "created", "id": 0}]) is True
    assert any_sent([{"event": "submitted", "order": 1, "id": 0}]) is True
    assert any_sent([{"event": "submitted", "order": 1}]) is True


def test_the_first_start_line_decides_whether_a_record_is_of_the_app():
    assert is_app([{"event": "start", "app": "qdevices"}]) is True
    assert is_app([{"event": "start"}, {"event": "start", "app": "qdevices"}]) is False
    assert is_app([{"event": "resume", "app": "qdevices"}]) is False
    assert is_app([]) is False


def test_the_seconds_of_a_decision_win_over_the_measured_seconds_and_none_gives_none():
    decision = {"event": "resolved", "order": 1, "over_limit": True, "counted_seconds": 100.0}
    assert counted([SENT, RESULT, decision], 1) == 100.0
    assert counted([SENT, RESULT], 1) == 2.5
    assert counted([SENT], 1) is None


def test_seconds_that_are_a_bool_or_nan_are_passed_over_for_the_next_key():
    assert counted([{**RESULT, "seconds": True, "device_seconds": 3.0, "wall_seconds": 4.0}], 1) == 3.0
    assert counted([{**RESULT, "seconds": float("nan"), "wall_seconds": 4.0}], 1) == 4.0
    assert counted([{**RESULT, "seconds": 2.5, "device_seconds": 3.0, "wall_seconds": 4.0}], 1) == 2.5
    assert counted([{**RESULT, "seconds": True}], 1) is None


def test_a_row_of_jobs_shows_failed_and_the_seconds_of_the_result_before_it():
    rows = monitor.job_rows([SENT, RESULT, FAILED])
    assert [row.split() for row in rows[1:]] == [["1", "J1", "J-1", "failed", "10", "2.500"], ["failed:", "-"]]


@pytest.mark.parametrize(("line", "word"), [
    (FAILED, "failed"),
    ({**FAILED, "event": "not_submitted"}, "not_submitted"),
    ({**FAILED, "event": "expired"}, "expired"),
    ({"event": "resolved", "order": 1, "none": True, "still_new": True}, "resolved_new"),
    ({"event": "resolved", "order": 1, "expired": True, "counted_seconds": 100.0}, "resolved_expired"),
])
def test_a_final_kind_that_no_golden_prints_is_the_plain_word_in_a_row_of_jobs(line, word):
    assert monitor.job_rows([SENT, line])[1].split() == ["1", "J1", "J-1", word, "-", "-"]


def test_a_row_of_jobs_says_not_sent_and_skipped_which_no_golden_prints():
    rows = monitor.job_rows([{"event": "stop", "order": 1, "name": "J1", "kind": "rule"},
                             {"event": "skip", "orders": [2]}])
    assert [row.split() for row in rows[1:]] == [["1", "J1", "-", "not", "sent", "-", "-"], ["stop:", "-"],
                                                 ["2", "-", "-", "skipped,", "never", "sent"]]


def test_a_name_of_0_is_no_name_and_shots_of_0_are_shots_in_a_row_of_jobs():
    line = {**FAILED, "name": 0, "shots": 0}
    assert monitor.job_rows([line])[1].split() == ["1", "-", "-", "failed", "0", "-"]       # a failed line gives no id
    assert monitor.job_rows([SENT, line])[1].split() == ["1", "J1", "J-1", "failed", "0", "-"]


def test_an_id_of_0_is_an_id_in_a_row_of_jobs():
    assert monitor.job_rows([{**SENT, "id": 0}])[1].split() == ["1", "J1", "0", "open", "(no", "state)", "-", "-"]


def test_a_result_with_a_failed_line_after_it_is_no_result_in_a_summary_or_in_a_call(tmp_path):
    assert tallied(write(tmp_path / "run1.jsonl", [SENT, RESULT])) == (1, 10, 2.5, 0, 2.5)
    assert tallied(write(tmp_path / "run2.jsonl", [SENT, RESULT, FAILED])) == (0, 0, 0, 0, 0)
    assert call_over([], prior=[SENT, RESULT]).results == {1: RESULT}
    assert call_over([], prior=[SENT, RESULT, FAILED]).results == {}


def test_resolve_over_limit_takes_no_order_with_a_failed_line_after_its_result(tmp_path, places, clock):
    conf = limits()
    assert send(write_manifest(tmp_path / "m", jobs=(("J1", 10),)), waited(), places, clock, conf, max_order=1) == 2
    rec = records_of(places)[0]
    with rec.open("a") as fh:
        fh.write(json.dumps(FAILED) + "\n")
    before = rec.read_bytes()
    assert counted(lines_of(rec), 1) == WAITED                 # the result stands, above the limit
    with pytest.raises(runner.Refused, match="it has no result with seconds"):
        over(rec, places, clock, conf)
    assert rec.read_bytes() == before


def test_the_last_submitted_line_wins_and_its_submitted_utc_comes_before_its_utc():
    first = {"event": "submitted", "order": 1, "submitted_utc": "first", "utc": "written"}
    assert call_over([first]).submitted_utc(1) == "first"
    assert call_over([first, {**first, "submitted_utc": "second"}]).submitted_utc(1) == "second"
    assert call_over([first, {"event": "submitted", "order": 1, "utc": "last"}]).submitted_utc(1) == "last"
    assert call_over([first]).submitted_utc(2) is None
    assert call_over([]).submitted_utc(1) is None


def test_the_last_submitting_line_gives_its_utc():
    lines = [{"event": "submitting", "order": 1, "utc": "first"}, {"event": "submitting", "order": 1, "utc": "last"}]
    assert call_over(lines).submitting_utc(1) == "last"
    assert call_over(lines).submitting_utc(2) is None
    assert call_over([]).submitting_utc(1) is None


def test_submit_never_sent_is_false_at_a_site_with_no_made_step():
    assert call_over([MADE]).submit_never_sent(1, 5) is False


def test_submit_never_sent_needs_the_made_step_of_that_job_and_no_submit_step():
    vlq = FakeSite("vlq")
    assert call_over([MADE], vlq).submit_never_sent(1, 5) is True
    assert call_over([MADE, UPLOADED], vlq).submit_never_sent(1, 5) is False
    assert call_over([MADE], vlq).submit_never_sent(1, 6) is False
    assert call_over([MADE], vlq).submit_never_sent(2, 5) is False


@pytest.mark.parametrize("order", [1.0, True])
def test_a_call_matches_an_order_by_equality_where_the_fold_passes_over_the_line(order):
    lines = [{"event": "submitting", "order": order, "utc": "asked"},
             {"event": "submitted", "order": order, "utc": "made"},
             {**MADE, "order": order}]
    call = call_over(lines, FakeSite("vlq"))
    assert (call.submitting_utc(1), call.submitted_utc(1), call.submit_never_sent(1, 5)) == ("asked", "made", True)
    assert any_sent(lines) is False
