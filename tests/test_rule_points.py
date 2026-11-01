"""What a rule of a user gets at each of the four points, what its verdict writes, and what a skip does."""

import copy
import hashlib
import json

import pytest
from fakes import QASM, STATE, TOKEN, FakeSite, events, lines_of, records_of, send, write_manifest
from test_call_paths import left_open, live, whole

from qdevices.redact import HIDDEN

POINTS = ("before_call", "before_job", "after_result", "on_refusal")
ORDER_AT = {"before_call": None, "before_job": 1, "after_result": 1, "on_refusal": 1}      # of a call of one order
HEAD = ["event", "utc", "app", "site", "machine", "project"]
SHA = hashlib.sha256(QASM).hexdigest()
JOB_1 = {"order": 1, "name": "J1", "file": "J1.qasm", "sha256": SHA, "shots": 10, "options": {}}
JOB_2 = {"order": 2, "name": "J2", "file": "J2.qasm", "sha256": SHA, "shots": 10, "options": {}}
STATE_KEYS = ["site", "machine", "project", "used_seconds", "budget_seconds", "job_seconds_limit", "wait_seconds",
              "site_max_shots", "max_shots", "max_shots_times_gates", "gate_count", "token_seconds_left", "in_window",
              "now_utc", "results", "sent", "skipped", "record"]
RESULT_1 = {"id": "J-1", "counts": {"1": 10}, "seconds": 1.5}
BEFORE_JOB = ("shots", "shots_times_gates", "budget", "token", "window", "my_before_job")


def keeper(seen: list, point: str):
    """A rule of a user that keeps its point and its arguments, and passes."""
    def hook(*args):
        seen.append((point, args))
        return {"rule": f"my_{point}", "passed": True}

    return hook


def keepers(seen: list) -> dict:
    """A rule of a user at each point, each keeping what it gets."""
    return {point: keeper(seen, point) for point in POINTS}


def got_at(seen: list, point: str) -> list:
    """The arguments of each call of the rule at this point."""
    return [args for at, args in seen if at == point]


def reaching(point: str) -> FakeSite:
    """A site at which a call that sends order 1 reaches this point."""
    return FakeSite(submits={1: ("refuse", 400)}) if point == "on_refusal" else FakeSite()


def state_of(rec, clock, **values) -> dict:
    """The state of a Euro-Q-Exa call on the fake site, with these values changed."""
    return {"site": "euroqexa", "machine": "M1", "project": "TEST-PROJECT", "used_seconds": 0.0,
            "budget_seconds": 1000, "job_seconds_limit": 100.0, "wait_seconds": 60.0, "site_max_shots": None,
            "max_shots": None, "max_shots_times_gates": None, "gate_count": 2, "token_seconds_left": None,
            "in_window": None, "now_utc": clock.utc().isoformat(), "results": {}, "sent": [], "skipped": [],
            "record": str(rec), **values}


def deface(value) -> None:
    """Empty every dict and list in a value."""
    if isinstance(value, (dict, list)):
        for item in list(value.values() if isinstance(value, dict) else value):
            deface(item)
        value.clear()


def broken(*args):
    """A rule of a user that raises."""
    raise ValueError("the hook broke")


def with_options(m):
    """The manifest at a path, with an option in each of its jobs."""
    data = json.loads(m.read_text())
    for job in data["jobs"]:
        job["options"] = {"no_modify": True}
    m.write_text(json.dumps(data))
    return m


def test_before_call_gets_the_read_alone_as_a_json_copy(tmp_path, places, clock):
    seen, checked = [], []
    site = FakeSite(read={"machine": "M1", "online": True, "table": {1: ("a", "b")}})
    site.validate = lambda job, read: checked.append(read["table"]) or []
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, user_rules=keepers(seen)) == 0
    assert got_at(seen, "before_call") == [({"machine": "M1", "online": True, "table": {"1": ["a", "b"]}},)]
    assert checked == [{1: ("a", "b")}] * 3                   # the check of each job reads what the site gave


def test_before_job_gets_the_job_with_no_text_and_the_state_with_its_keys_in_order(tmp_path, places, clock):
    seen = []
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=2, user_rules=keepers(seen)) == 0
    rec = records_of(places)[0]
    (job_1, state_1), (job_2, state_2) = got_at(seen, "before_job")
    assert list(job_1.items()) == list(JOB_1.items()) and list(job_2.items()) == list(JOB_2.items())
    assert list(state_1) == STATE_KEYS and list(state_2) == STATE_KEYS
    assert state_1 == state_of(rec, clock)
    assert state_2 == state_of(rec, clock, used_seconds=1.5, results={"1": RESULT_1}, sent=[1])


def test_after_result_gets_the_job_the_result_line_and_the_state(tmp_path, places, clock):
    seen = []
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1, user_rules=keepers(seen)) == 0
    rec = records_of(places)[0]
    [(job, result, state)] = got_at(seen, "after_result")
    assert list(job.items()) == list(JOB_1.items())
    assert list(result.items()) == [("order", 1), ("name", "J1"), ("id", "J-1"), ("shots", 10), ("counts", {"1": 10}),
                                    ("seconds", 1.5), ("seconds_kind", "device"), ("wall_seconds", 0.0),
                                    ("published_seconds", None), ("polls", 1), ("recovered", False)]
    assert list(state) == STATE_KEYS
    assert state == state_of(rec, clock, used_seconds=1.5, results={"1": RESULT_1}, sent=[1])


@pytest.mark.parametrize("answers, info", [
    ({"submits": {1: ("refuse", 400)}},
     {"kind": "refused", "id": None, "reason": "HTTP 400", "http_status": 400, "body": "cz"}),
    ({"states": {"J-1": [STATE("FAILED", final=True)]}},
     {"kind": "failed", "id": "J-1", "state": "FAILED", "reason": "the job ended FAILED"}),
], ids=["refused", "failed"])
def test_on_refusal_gets_the_job_and_what_happened(tmp_path, places, clock, answers, info):
    seen = []
    site = FakeSite(**answers)
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, user_rules=keepers(seen)) == 0
    [(job, given)] = got_at(seen, "on_refusal")
    assert list(job.items()) == list(JOB_1.items())
    assert list(given.items()) == list(info.items())


@pytest.mark.parametrize("answers, code, reads", [
    ({"read": {"machine": "M1", "online": False}}, 2, 0),
    ({"submits": {1: ("refuse", 400)}}, 2, 1),
    ({"states": {"J-1": [STATE("FAILED", final=True)]}}, 2, 1),
    ({}, 0, 2),
], ids=["a stop at before_call", "on_refusal of a refused job", "on_refusal of a failed job", "a job that ends well"])
def test_the_state_is_made_only_at_before_job_and_at_after_result(tmp_path, places, clock, answers, code, reads):
    site, asked = FakeSite(**answers), []
    site.token_seconds_left = lambda: asked.append(1)
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == code
    assert len(asked) == reads


def test_a_token_that_cannot_be_read_leaves_a_failed_job_on_a_resume_a_refusal(tmp_path, places, clock):
    def no_token():
        raise RuntimeError("the time left on the token cannot be read")

    m, rec = left_open(tmp_path, places, clock)
    site = FakeSite(states={"J-1": [STATE("FAILED", final=True)]})
    site.token_seconds_left = no_token
    assert send(m, site, places, clock, resume=rec) == 2
    assert events(rec, "stop")[-1]["rule"] == "refusal"


def test_a_hook_that_changes_its_arguments_changes_neither_the_record_nor_the_call(tmp_path, places, clock):
    seen, checked = [], []

    def spoiler(point):
        def hook(*args):
            seen.append((point, copy.deepcopy(args)))
            deface(list(args))
            return {"rule": "spoil", "passed": True}

        return hook

    site = FakeSite(submits={2: ("refuse", 400)})
    site.validate = lambda job, read: checked.append(read["online"]) or []
    user = {point: spoiler(point) for point in POINTS}
    m = with_options(write_manifest(tmp_path / "m"))
    assert send(m, site, places, clock, max_order=3, user_rules=user) == 0
    rec = records_of(places)[0]
    assert checked == [True] * 3
    assert [line["shots"] for line in events(rec, "submitting")] == [10, 10, 10]
    assert [line["options"] for line in events(rec, "submitting")] == [{"no_modify": True}] * 3
    assert site.shots == {"J-1": 10, "J-3": 10}
    assert [line["counts"] for line in events(rec, "result")] == [{"1": 10}, {"1": 10}]
    assert [line["order"] for line in events(rec, "rule") if line["rule"] == "spoil"] == [None, 1, 1, 2, 2, 3, 3]
    jobs_and_states = got_at(seen, "before_job")
    assert [job["shots"] for job, _ in jobs_and_states] == [10, 10, 10]
    assert [state["sent"] for _, state in jobs_and_states] == [[], [1], [1, 2]]
    assert jobs_and_states[2][1]["results"] == {"1": RESULT_1}


def test_at_each_point_the_generic_rules_come_first_and_the_user_rule_last(tmp_path, places, clock):
    site = FakeSite(submits={2: ("refuse", 400)})
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=2, user_rules=keepers([])) == 0
    rows = [(line["point"], line["order"], line["rule"]) for line in events(records_of(places)[0], "rule")]
    assert rows == [("before_call", None, "machine"), ("before_call", None, "site_status"),
                    ("before_call", None, "my_before_call"), *[("before_job", 1, rule) for rule in BEFORE_JOB],
                    ("after_result", 1, "all_shots"), ("after_result", 1, "job_time"),
                    ("after_result", 1, "my_after_result"), *[("before_job", 2, rule) for rule in BEFORE_JOB],
                    ("on_refusal", 2, "my_on_refusal")]


def test_every_rule_of_a_point_runs_and_is_written_and_the_stop_names_the_first_not_met(tmp_path, places, clock):
    asked = []
    user = {"before_job": lambda job, state: asked.append(job["order"]) or {"rule": "mine", "passed": False,
                                                                            "reason": "no"}}
    m = write_manifest(tmp_path / "m", jobs=(("J1", 300),))
    assert send(m, FakeSite(max_shots=200), places, clock, max_order=1, user_rules=user) == 2
    rec = records_of(places)[0]
    assert [(line["rule"], line["passed"]) for line in events(rec, "rule") if line["point"] == "before_job"] == [
        ("shots", False), ("shots_times_gates", True), ("budget", True), ("token", True), ("window", True),
        ("mine", False)]
    assert asked == [1]
    assert events(rec, "stop")[-1]["rule"] == "shots"


@pytest.mark.parametrize("point", ["before_call", "before_job", "after_result"])
def test_a_user_rule_of_another_point_leaves_the_generic_rule_of_on_refusal(tmp_path, places, clock, point):
    site = FakeSite(submits={1: ("refuse", 400)})
    user = {point: keeper([], point)}
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, user_rules=user) == 2
    rec = records_of(places)[0]
    assert [line["rule"] for line in events(rec, "rule") if line["point"] == "on_refusal"] == ["refusal"]
    assert events(rec, "stop")[-1]["rule"] == "refusal"


@pytest.mark.parametrize("point", POINTS)
def test_a_hook_that_raises_gives_a_failed_verdict_with_its_text_and_its_stop(tmp_path, places, clock, point):
    site = reaching(point)
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, user_rules={point: broken}) == 2
    rec = records_of(places)[0]
    text = f"the hook {point} raised ValueError: the hook broke"
    assert list(events(rec, "rule")[-1].items()) == whole("rule", clock, point=point, order=ORDER_AT[point], rule=point,
                                                          passed=False, reason=text, skip=[])
    assert list(lines_of(rec)[-1].items()) == whole("stop", clock, reason=f"rule {point}: {text}", kind="rule",
                                                    rule=point, order=ORDER_AT[point])
    sent = [] if point in ("before_call", "before_job") else [("submit", 1)]
    assert [c for c in site.calls if c[0] == "submit"] == sent


def raising(error: BaseException):
    """A rule of a user that raises this error."""
    def hook(*args):
        raise error

    return hook


@pytest.mark.parametrize("point", POINTS)
@pytest.mark.parametrize("error, text", [(SystemExit(5), "SystemExit: 5"), (GeneratorExit(), "GeneratorExit: ")],
                         ids=["SystemExit", "GeneratorExit"])
def test_a_hook_that_raises_an_exit_gives_a_failed_verdict_and_its_stop(tmp_path, places, clock, point, error, text):
    site = reaching(point)
    user = {point: raising(error)}
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, user_rules=user) == 2
    rec = records_of(places)[0]
    reason = f"the hook {point} raised {text}"
    assert (events(rec, "rule")[-1]["passed"], events(rec, "rule")[-1]["reason"]) == (False, reason)
    assert list(lines_of(rec)[-1].items()) == whole("stop", clock, reason=f"rule {point}: {reason}", kind="rule",
                                                    rule=point, order=ORDER_AT[point])


def test_a_hook_that_raises_an_interrupt_is_still_an_interrupt(tmp_path, places, clock):
    user = {"before_job": raising(KeyboardInterrupt())}
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1, user_rules=user) == 130
    stop = lines_of(records_of(places)[0])[-1]
    assert (stop["event"], stop["kind"]) == ("stop", "interrupt")


@pytest.mark.parametrize("point", POINTS)
@pytest.mark.parametrize("answer, rule", [
    (5, None), ({"passed": 1}, None), ({"rule": "mine", "passed": True, "skip": 3}, "mine"),
    ({"rule": "mine", "passed": True, "skip": [True]}, "mine"),
], ids=["a number", "passed not a bool", "a skip not a list", "a skip with a bool"])
def test_a_hook_that_answers_no_verdict_or_a_bad_skip_gives_a_failed_verdict_and_its_stop(
        tmp_path, places, clock, point, answer, rule):
    user = {point: lambda *args: answer}
    assert send(write_manifest(tmp_path / "m"), reaching(point), places, clock, max_order=1, user_rules=user) == 2
    rec = records_of(places)[0]
    line, stop = events(rec, "rule")[-1], lines_of(rec)[-1]
    name = rule or point
    assert (line["point"], line["order"], line["rule"], line["passed"]) == (point, ORDER_AT[point], name, False)
    assert line["reason"].startswith(f"the hook {point} ")      # its words are in a golden
    assert (stop["event"], stop["kind"], stop["rule"], stop["order"]) == ("stop", "rule", name, ORDER_AT[point])


def test_the_keys_of_the_line_and_its_base_fields_leave_a_verdict(tmp_path, places, clock):
    own = {"rule": "mine", "passed": True, "event": "x", "utc": "x", "point": "x", "order": 9, "app": "a", "site": "s",
           "machine": "theirs", "project": "p", "zeta": 1}
    user = {"before_job": lambda job, state: own}
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1, user_rules=user) == 0
    line = next(row for row in events(records_of(places)[0], "rule") if row["rule"] == "mine")
    assert list(line.items()) == whole("rule", clock, point="before_job", order=1, rule="mine", passed=True, zeta=1,
                                       skip=[], reason=None)


@pytest.mark.parametrize("key, shown", [("self", "'self'"), (1, "1")], ids=["self", "a number"])
def test_a_verdict_with_a_key_that_cannot_be_a_keyword_of_the_write_is_a_failed_verdict(
        tmp_path, places, clock, capsys, key, shown):
    user = {"before_job": lambda job, state: {"rule": "mine", "passed": True, key: 1}}
    site = FakeSite()
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, user_rules=user) == 2
    rec = records_of(places)[0]
    reason = f"the hook before_job gave a key that a record line cannot hold: {shown}"
    assert list(events(rec, "rule")[-1].items()) == whole("rule", clock, point="before_job", order=1, rule="mine",
                                                          passed=False, reason=reason, skip=[])
    assert list(lines_of(rec)[-1].items()) == whole("stop", clock, reason=f"rule mine: {reason}", kind="rule",
                                                    rule="mine", order=1)
    assert ("submit", 1) not in site.calls
    assert "FAILED: an error of the program" not in capsys.readouterr().err


@pytest.mark.parametrize("point", POINTS)
def test_the_key_order_of_a_rule_line_of_a_user_at_each_point(tmp_path, places, clock, point):
    user = {point: lambda *args: {"zeta": 1, "passed": True, "rule": "mine"}}
    assert send(write_manifest(tmp_path / "m"), reaching(point), places, clock, max_order=1, user_rules=user) == 0
    line = next(row for row in events(records_of(places)[0], "rule") if row["rule"] == "mine")
    assert list(line) == [*HEAD, "point", "order", "zeta", "passed", "rule", "skip", "reason"]
    assert (line["point"], line["order"]) == (point, ORDER_AT[point])


def test_the_key_order_of_a_rule_line_of_a_generic_rule(tmp_path, places, clock):
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1) == 0
    rows = {row["rule"]: row for row in events(records_of(places)[0], "rule")}
    assert list(rows["shots"]) == [*HEAD, "point", "order", "rule", "passed", "reason", "skip", "shots", "limit"]
    assert list(rows["machine"]) == [*HEAD, "point", "order", "rule", "passed", "reason", "skip"]


@pytest.mark.parametrize("passed, printed, code", [
    (True, "  rule mine: pass", 0),
    (False, "  rule mine: NOT MET: why not", 2),
], ids=["pass", "not met"])
def test_a_verdict_note_is_printed_after_its_rule_line(tmp_path, places, clock, passed, printed, code):
    said, on_disk = [], []

    def say(text):
        said.append(text)
        if text == "  NOTE: look here":
            on_disk.append(lines_of(records_of(places)[0])[-1])

    user = {"before_job": lambda job, state: {"rule": "mine", "passed": passed, "reason": "why not",
                                              "note": "look here"}}
    assert live(write_manifest(tmp_path / "m"), FakeSite(), places, clock, say, max_order=1, user_rules=user) == code
    assert said[said.index(printed) + 1] == "  NOTE: look here"
    [line] = on_disk
    assert (line["event"], line["rule"], line["note"]) == ("rule", "mine", "look here")
    assert list(line) == [*HEAD, "point", "order", "rule", "passed", "reason", "note", "skip"]


def test_the_screen_the_stop_and_the_record_filter_a_token_in_a_verdict(tmp_path, places, clock):
    user = {"before_job": lambda job, state: {"rule": "mine", "passed": False, "reason": f"bad {TOKEN}",
                                              "note": f"see {TOKEN}"}}
    said = []
    m = write_manifest(tmp_path / "m")
    assert live(m, FakeSite(), places, clock, said.append, max_order=1, user_rules=user) == 2
    assert f"  rule mine: NOT MET: bad {HIDDEN}" in said and f"  NOTE: see {HIDDEN}" in said
    assert f"STOP: rule mine: bad {HIDDEN}" in said
    assert not [line for line in said if TOKEN in line]
    assert TOKEN not in records_of(places)[0].read_text()


def test_a_skip_writes_its_line_with_the_orders_sorted_and_those_orders_are_never_sent(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10), ("J3", 10), ("J4", 10)))
    user = {"after_result": lambda job, result, state: {"rule": "pick", "passed": True,
                                                        "skip": [4, 2] if job["order"] == 1 else []}}
    site, said = FakeSite(), []
    assert live(m, site, places, clock, said.append, max_order=4, user_rules=user) == 0
    rec = records_of(places)[0]
    [skip] = events(rec, "skip")
    assert list(skip.items()) == whole("skip", clock, orders=[2, 4], after_order=1, rules=["pick"])
    assert next(row for row in events(rec, "rule") if row["rule"] == "pick")["skip"] == [4, 2]    # as the hook gave it
    assert "  SKIP: the orders [2, 4] are not sent" in said
    assert "[2/4] J2: skipped by a rule" in said and "[4/4] J4: skipped by a rule" in said
    assert [c[1] for c in site.calls if c[0] == "submit"] == [1, 3]
    end = lines_of(rec)[-1]
    assert (end["event"], end["left"], end["results"]) == ("end", [], 2)


@pytest.mark.parametrize("point", POINTS)
def test_a_skip_at_each_point_names_the_order_it_came_after(tmp_path, places, clock, point):
    once = [[3]]
    user = {point: lambda *args: {"rule": "pick", "passed": True, "skip": once.pop() if once else []}}
    site = reaching(point)
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=3, user_rules=user) == 0
    rec = records_of(places)[0]
    assert list(events(rec, "skip")[0].items()) == whole("skip", clock, orders=[3], after_order=ORDER_AT[point],
                                                         rules=["pick"])
    assert [c[1] for c in site.calls if c[0] == "submit"] == [1, 2]


def test_the_state_of_the_next_order_holds_the_skip_and_a_resume_keeps_it(tmp_path, places, clock):
    seen = []
    hooks = {"after_result": lambda job, result, state: {"rule": "pick", "passed": True, "skip": [2]},
             "before_job": keeper(seen, "before_job")}
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10), ("J3", 10), ("J4", 10)))
    assert send(m, FakeSite(), places, clock, max_order=1, user_rules=hooks) == 0
    rec = records_of(places)[0]
    site, said = FakeSite(), []
    user = {"before_job": keeper(seen, "before_job")}
    assert live(m, site, places, clock, said.append, resume=rec, max_order=3, user_rules=user) == 0
    assert "[2/4] J2: skipped by a rule" in said
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 3)]
    assert [state["skipped"] for _, state in got_at(seen, "before_job")] == [[], [2]]
    assert lines_of(rec)[-1]["left"] == [4]


@pytest.mark.parametrize("skip, bad", [([1], [1]), ([9], [9]), ([0], [0]), ([2, 9, 1], [1, 9])],
                         ids=["sent", "above", "below", "a good one with both"])
def test_a_skip_of_an_order_sent_or_out_of_range_stops_with_its_text_and_writes_no_skip(
        tmp_path, places, clock, skip, bad):
    user = {"after_result": lambda job, result, state: {"rule": "pick", "passed": True, "skip": skip}}
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=3, user_rules=user) == 2
    rec = records_of(places)[0]
    assert events(rec, "skip") == []
    assert list(lines_of(rec)[-1].items()) == whole(
        "stop", clock, reason=f"a rule names orders to skip that were sent or do not exist: {bad}", kind="rule",
        order=1)


def test_a_failed_verdict_with_a_skip_stops_and_writes_no_skip(tmp_path, places, clock):
    user = {"after_result": lambda job, result, state: {"rule": "pick", "passed": False, "reason": "no", "skip": [2]}}
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=3, user_rules=user) == 2
    rec = records_of(places)[0]
    assert events(rec, "skip") == []
    assert lines_of(rec)[-1]["reason"] == "rule pick: no"


@pytest.mark.parametrize("skip", [0, "", None, {}, []], ids=["0", "a text", "None", "a dict", "a list"])
def test_a_skip_that_is_empty_or_false_is_no_skip(tmp_path, places, clock, skip):
    user = {"before_job": lambda job, state: {"rule": "pick", "passed": True, "skip": skip}}
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1, user_rules=user) == 0
    rec = records_of(places)[0]
    assert next(row for row in events(rec, "rule") if row["rule"] == "pick")["skip"] == []
    assert events(rec, "skip") == []


@pytest.mark.parametrize("point, after_order", [("before_call", None), ("before_job", 1)])
def test_a_skip_of_the_order_under_way_is_not_sent_and_the_call_goes_on_with_the_next(
        tmp_path, places, clock, point, after_order):
    once = [[1]]
    user = {point: lambda *args: {"rule": "pick", "passed": True, "skip": once.pop() if once else []}}
    site, said = FakeSite(), []
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10)))
    assert live(m, site, places, clock, said.append, max_order=2, user_rules=user) == 0
    rec = records_of(places)[0]
    [skip] = events(rec, "skip")
    assert (skip["orders"], skip["after_order"]) == ([1], after_order)
    assert said[said.index("  SKIP: the orders [1] are not sent") + 1] == "  order 1 (J1): skipped by a rule, not sent"
    assert [c[1] for c in site.calls if c[0] in ("prepare", "submit")] == [2, 2]
    assert [e["order"] for e in events(rec, "submitting")] == [2]
    assert [e["order"] for e in events(rec, "result")] == [2]
    end = lines_of(rec)[-1]
    assert (end["event"], end["left"], end["results"]) == ("end", [], 1)


def test_a_skip_of_the_order_under_way_stays_skipped_at_a_resume(tmp_path, places, clock):
    user = {"before_job": lambda job, state: {"rule": "pick", "passed": True, "skip": [1]}}
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10)))
    assert send(m, FakeSite(), places, clock, max_order=1, user_rules=user) == 0
    rec = records_of(places)[0]
    assert lines_of(rec)[-1]["left"] == [2]
    site, said = FakeSite(), []
    assert live(m, site, places, clock, said.append, resume=rec, max_order=2) == 0
    assert "[1/2] J1: skipped by a rule" in said
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 2)]
