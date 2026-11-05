"""The scope of `resolve --unreadable`, by the kind of each result_error stop, and the texts that name it.

An answer that could not be used is taken at two calls 10 minutes or more apart. No usable answer (missed polls, a
redirect or an HTTP error of 400 or more, or a stop line written before 0.2.0) is taken at two calls 24 hours or more
apart.
"""

import json
import re
import shlex
from datetime import UTC, datetime, timedelta

import pytest
from fakes import cfg, events, lines_of, records_of
from fakes.piastq import Broker, answer, run_broker

from qdevices import cli, monitor, resolve, runner
from qdevices.resolve.stops import Stops

UNREADABLE = answer(200, json={"result": [["a"]]})      # a shot that is not bits: an answer that could not be used
DOWN = answer(503, text="")                             # a missed poll at each read, up to wait_seconds
FORBIDDEN = answer(403, text="")                        # an HTTP error, which ends the wait at once
REDIRECT = answer(302, headers={"location": "/login"})  # a redirect, as to a login page: no usable answer
TEN, DAY = resolve.EXPIRED_MINUTES * 60, resolve.UNANSWERED_HOURS * 3600
NOTE = "Collect it the same day: how long the broker keeps a result is not published"
FIRST = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
READ = {"missed": None, "http_status": None}            # the fields of a stop on an answer that could not be used
MISSED = {"missed": "HTTP 503", "http_status": 503}     # of a stop after missed polls
ERROR = {"missed": None, "http_status": 404}            # of a stop at an HTTP error
OLD = {"http_status": None}                             # of a stop line written before 0.2.0: no key missed
WHY = {
    "one read": "one call only got an answer that could not be used: resume once more, 10 minutes or more later",
    "reads close": "the calls that got an answer that could not be used are less than 10 minutes apart: resume "
                   "once more later",
    "one unanswered": "one call only got that stop, with no usable answer: resume later",
    "unanswered close": "the last call got no usable answer, and the calls that got that stop are less than 24 hours "
                        "apart: resume later",
}


def unreadable(rec, places, clock) -> str:
    return resolve.resolve(rec, 1, None, places=places, clock=clock, host="host-a", decision="unreadable", cfg=cfg())


def refused(rec, places, clock) -> str:
    with pytest.raises(runner.Refused) as caught:
        unreadable(rec, places, clock)
    return str(caught.value)


def command(rec) -> str:
    return f"qdevices resolve {shlex.quote(str(rec))} 1 --unreadable"


def kinds(rec) -> list[tuple]:
    return [(s["kind"], s["missed"], s["http_status"], s["missed_polls"]) for s in events(rec, "stop")]


def stops(*found: tuple[float, dict]) -> Stops:
    """The stops of order 1, each (seconds after the first, its fields), at a call of its own."""
    lines = []
    for seconds, fields in found:
        utc = (FIRST + timedelta(seconds=seconds)).isoformat()
        lines += [{"event": "resume"}, {"event": "stop", "order": 1, "kind": "result_error", **fields, "utc": utc}]
    return Stops.of(lines, 1)


# --------------------------------------------------------------------- the rule, on the lines alone

@pytest.mark.parametrize("fields, kind", [
    (READ, True), ({"missed": None, "http_status": 200}, True), ({"missed": None, "http_status": 302}, False),
    ({"missed": None, "http_status": 300}, False), (ERROR, False), ({"missed": None, "http_status": 400}, False),
    (MISSED, False), ({"missed": "no answer", "http_status": None}, False),
    ({"missed": "busy", "http_status": 422}, False), (OLD, False), ({}, False)], ids=repr)
def test_a_stop_got_an_answer_that_could_not_be_used_when_missed_is_null_and_no_redirect_or_http_error(fields, kind):
    assert resolve.answered(fields) is kind


CASES = {      # case: the result_error stops (seconds after the first, fields), each at a call; why it is refused
    "two reads ten minutes apart": (((0, READ), (TEN, READ)), None),
    "two reads a second short": (((0, READ), (TEN - 1, READ)), WHY["reads close"]),
    "one read": (((0, READ),), WHY["one read"]),
    "missed polls ten minutes apart": (((0, MISSED), (TEN, MISSED)), WHY["unanswered close"]),
    "missed polls a second short of a day": (((0, MISSED), (DAY - 1, MISSED)), WHY["unanswered close"]),
    "missed polls a day apart": (((0, MISSED), (DAY, MISSED)), None),
    "one call with missed polls": (((0, MISSED),), WHY["one unanswered"]),
    "an http error ten minutes apart": (((0, ERROR), (TEN, ERROR)), WHY["unanswered close"]),
    "an http error a day apart": (((0, ERROR), (DAY, ERROR)), None),
    "old lines ten minutes apart": (((0, OLD), (TEN, OLD)), WHY["unanswered close"]),
    "old lines a day apart": (((0, OLD), (DAY, OLD)), None),
    "a read, then missed polls": (((0, READ), (TEN, MISSED)), WHY["unanswered close"]),
    "missed polls, then a read": (((0, MISSED), (TEN, READ)), WHY["one read"]),
    "a read, missed polls, a read": (((0, READ), (60, MISSED), (TEN, READ)), None),
    "missed polls, then a read a day later": (((0, MISSED), (DAY, READ)), None),
}


@pytest.mark.parametrize("case", list(CASES))
def test_the_rule_of_unreadable_by_the_kind_of_each_stop(case):
    found, why = CASES[case]
    assert stops(*found).unreadable() == why


# --------------------------------------------------------------------- the stops a call writes, and the decision

def test_an_answer_that_could_not_be_used_names_the_command_and_is_taken_ten_minutes_later(tmp_path, places, clock):
    broker = Broker(results=[UNREADABLE])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    clock.t += TEN
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert kinds(rec) == [("result_error", None, None, 0)] * 2
    assert events(rec, "stop")[-1]["reason"] == (
        "order 1 (J1), job p-1: the result cannot be read: a shot of the result is not a list of bits. The order "
        f"stays open; a resume reads it again. {NOTE}. When two calls 10 minutes or more apart got this stop, record "
        f"it with: {command(rec)}")
    assert "it counts at 100 s" in unreadable(rec, places, clock)
    assert "100.0 s counted (1 orders resolved over the limit, expired, unreadable or gone)" in monitor.run_line(
        monitor.summary(rec))


def test_missed_polls_say_resume_later_and_are_taken_only_a_day_after_the_first(tmp_path, places, clock):
    broker = Broker(results=[DOWN])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    clock.t += TEN
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert kinds(rec) == [("result_error", "HTTP 503", 503, 6)] * 2
    assert events(rec, "stop")[-1]["reason"] == (
        "order 1 (J1), job p-1: the result cannot be read: HTTP 503 to GET /tasks/p-1/results, after 6 missed polls. "
        f"The order stays open; resume later. {NOTE}. When two calls 24 hours or more apart got this stop, record it "
        f"with: {command(rec)}")
    assert refused(rec, places, clock).endswith(f"({WHY['unanswered close']})")
    clock.t += DAY
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert "it counts at 100 s" in unreadable(rec, places, clock)
    assert broker.count("POST", "/tasks") == 1


def test_an_http_error_at_the_read_of_the_result_is_no_usable_answer(tmp_path, places, clock):
    broker = Broker(results=[FORBIDDEN])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    clock.t += TEN
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert kinds(rec) == [("result_error", None, 403, 0)] * 2
    assert "The order stays open; resume later." in events(rec, "stop")[-1]["reason"]
    assert refused(rec, places, clock).endswith(f"({WHY['unanswered close']})")


def test_a_redirect_at_the_read_of_the_result_is_no_usable_answer_and_is_taken_a_day_later(tmp_path, places, clock):
    broker = Broker(results=[REDIRECT])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    clock.t += TEN
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert kinds(rec) == [("result_error", None, 302, 0)] * 2
    assert events(rec, "stop")[-1]["reason"] == (
        "order 1 (J1), job p-1: the result cannot be read: HTTP 302 to GET /tasks/p-1/results. The order stays "
        f"open; resume later. {NOTE}. When two calls 24 hours or more apart got this stop, record it with: "
        f"{command(rec)}")
    assert refused(rec, places, clock).endswith(f"({WHY['unanswered close']})")
    clock.t += DAY
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert "it counts at 100 s" in unreadable(rec, places, clock)


def test_the_stop_lines_of_an_app_before_0_2_0_are_no_usable_answer(tmp_path, places, clock):
    broker = Broker(results=[UNREADABLE])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    clock.t += TEN
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    old = [{k: v for k, v in line.items() if (line["event"], k) != ("stop", "missed")} for line in lines_of(rec)]
    rec.write_text("".join(json.dumps(line) + "\n" for line in old), encoding="utf-8")     # no key missed
    assert refused(rec, places, clock).endswith(f"({WHY['unanswered close']})")
    clock.t += DAY
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1                       # every stop counts
    assert "it counts at 100 s" in unreadable(rec, places, clock)


def test_answers_that_could_not_be_used_around_missed_polls_are_taken_ten_minutes_apart(tmp_path, places, clock):
    broker = Broker(results=[UNREADABLE])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    broker.results = [DOWN]
    clock.t += TEN
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert refused(rec, places, clock).endswith(f"({WHY['unanswered close']})")
    broker.results = [UNREADABLE]
    assert run_broker(tmp_path, places, clock, broker, resume=rec) == 1
    assert [stop["missed"] for stop in events(rec, "stop")] == [None, "HTTP 503", None]
    assert "it counts at 100 s" in unreadable(rec, places, clock)


def test_the_refusal_names_both_cases(tmp_path, places, clock):
    broker = Broker(results=[UNREADABLE])
    assert run_broker(tmp_path, places, clock, broker) == 1
    rec = records_of(places)[0]
    assert refused(rec, places, clock) == (
        f"order 1 of {rec} is open: --unreadable takes only an open order whose last stop is result_error, after two "
        "calls 10 minutes or more apart got an answer that could not be used, or two calls 24 hours or more apart "
        f"got that stop ({WHY['one read']})")


# --------------------------------------------------------------------- the decisions that count seconds

def test_each_decision_that_counts_seconds_is_a_flag_of_resolve(tmp_path):
    for name in resolve.DECISIONS:
        args = cli.parser().parse_args(["resolve", str(tmp_path / "r.jsonl"), "1", resolve.flag(name)])
        assert getattr(args, name) is True and args.command == "resolve"


def test_usage_and_runs_name_the_decisions_that_count_seconds():
    note = monitor.usage([], {})[-1]
    flags = "`qdevices resolve --over-limit`, `--expired`, `--unreadable` or `--gone`"
    assert re.search(f"a decision of {re.escape(flags)} in place of the measured ones", note)
    assert resolve.joined(["a", "b", "c"]) == "a, b or c" and resolve.joined(["a", "b"], "and") == "a and b"
    assert resolve.joined(["a"]) == "a" and list(resolve.DECISIONS) == ["over_limit", "expired", "unreadable", "gone"]
