"""Unit tables of the rules: generic rules, the fixed verdict form, rules file refusals, and user hooks in a send."""

import json

import pytest
from fakes import STATE, FakeSite, lines_of, records_of, send, write_manifest

from qdevices import rulebook, rules

FLAGS = {"QPU_status": True, "QCCW_status": True, "queue_available": True, "total_status": True}
LIMIT = {"max_shots_times_gates": 3_000_000}
JOB_TIME = {"job_seconds_limit": 100.0}
VLQ = {"site": "vlq", "wait_seconds": 900.0}
GENERIC = [             # (case, rule, arguments); the verdict of each is in the golden
    ("machine_ready, not a member", rules.machine_ready, ({"member": False, "lexis_project": "TEST-LEXIS"},)),
    ("machine_ready, not online", rules.machine_ready, ({"machine": "M1", "online": False},)),
    ("machine_ready, online is not true", rules.machine_ready, ({"machine": "M1", "online": "yes"},)),
    ("machine_ready, ready", rules.machine_ready, ({"machine": "M1", "online": True, "member": True},)),
    ("site_status, no status", rules.site_status, ({"machine": "M1"},)),
    ("site_status, not read", rules.site_status, ({"status": {"flags": None, "error": "HTTP 500"}},)),
    ("site_status, not an object", rules.site_status, ({"status": "UP"},)),
    ("site_status, two rows down", rules.site_status, ({"status": {"flags": {**FLAGS, "QPU_status": False,
                                                                              "total_status": False}}},)),
    ("site_status, a row unclear", rules.site_status, ({"status": {"flags": {**FLAGS, "queue_available": 1}}},)),
    ("site_status, up", rules.site_status, ({"status": {"flags": FLAGS}},)),
    ("shot_limit, above the site", rules.shot_limit, ({"shots": 201}, {"site_max_shots": 200, "max_shots": None})),
    ("shot_limit, above the own", rules.shot_limit, ({"shots": 150}, {"site_max_shots": 200, "max_shots": 100})),
    ("shot_limit, no limit", rules.shot_limit, ({"shots": 10 ** 6}, {})),
    ("gate_limit, no limit", rules.gate_limit, ({"shots": 10 ** 9}, {"max_shots_times_gates": None, "gate_count": 3})),
    ("gate_limit, not counted", rules.gate_limit, ({"shots": 10}, {**LIMIT, "gate_count": None})),
    ("gate_limit, at the limit", rules.gate_limit, ({"shots": 10 ** 6}, {**LIMIT, "gate_count": 3})),
    ("gate_limit, above", rules.gate_limit, ({"shots": 10 ** 6 + 1}, {**LIMIT, "gate_count": 3})),
    ("budget, no budget_seconds", rules.budget, ({}, {"used_seconds": 0.0, "job_seconds_limit": 300.0,
                                                       "budget_seconds": None})),
    ("budget, within", rules.budget, ({}, {"used_seconds": 899.5, **JOB_TIME, "budget_seconds": 1000})),
    ("budget, above", rules.budget, ({}, {"used_seconds": 900.25, **JOB_TIME, "budget_seconds": 1000})),
    ("token_time, another site", rules.token_time, ({}, {"site": "euroqexa", "token_seconds_left": None})),
    ("token_time, not read", rules.token_time, ({}, {**VLQ, "token_seconds_left": None})),
    ("token_time, too short", rules.token_time, ({}, {**VLQ, "token_seconds_left": 1799.0})),
    ("token_time, enough", rules.token_time, ({}, {**VLQ, "token_seconds_left": 1800.0})),
    ("token_time, twice the wait", rules.token_time, ({}, {**VLQ, "wait_seconds": 1800.0,
                                                            "token_seconds_left": 3000.0})),
    ("window, outside", rules.window, ({}, {"in_window": False})),
    ("window, inside", rules.window, ({}, {"in_window": True})),
    ("window, no window", rules.window, ({}, {"in_window": None})),
    ("all_shots, no counts", rules.all_shots, ({"shots": 10}, {"counts": None}, {})),
    ("all_shots, a key not of bits", rules.all_shots, ({"shots": 10}, {"counts": {"2": 10}}, {})),
    ("all_shots, a count that is a bool", rules.all_shots, ({"shots": 1}, {"counts": {"1": True}}, {})),
    ("all_shots, fewer", rules.all_shots, ({"shots": 10}, {"counts": {"0": 4, "1": 5}}, {})),
    ("all_shots, all", rules.all_shots, ({"shots": 10}, {"counts": {"0": 4, "1": 6}}, {})),
    ("job_time, no seconds", rules.job_time, ({"order": 2}, {}, JOB_TIME)),
    ("job_time, below zero", rules.job_time, ({"order": 2}, {"seconds": -1.0}, JOB_TIME)),
    ("job_time, above", rules.job_time, ({"order": 2}, {"seconds": 500.0}, {**JOB_TIME, "record": "a b/run.jsonl"})),
    ("job_time, above, no record", rules.job_time, ({"order": 2}, {"seconds": 500}, JOB_TIME)),
    ("job_time, within", rules.job_time, ({"order": 2}, {"seconds": 1.5}, JOB_TIME)),
    ("stop_on_refusal", rules.stop_on_refusal, ({"order": 1, "name": "J1"}, {"kind": "refused", "reason": "HTTP 400"})),
    ("stop_on_refusal, no reason", rules.stop_on_refusal, ({"order": 1, "name": "J1"}, {"kind": "failed"})),
]
CHECKED = [             # (case, what a hook answered); each verdict is in the golden
    ("own keys", {"zeta": 1, "passed": True, "rule": "mine", "alpha": [2]}),
    ("failed with no reason", {"passed": False, "rule": "mine"}),
    ("no rule", {"passed": True}),
    ("a rule that is a number", {"passed": True, "rule": 7}),
    ("not a dict", 5),
    ("passed is not a bool", {"passed": 1}),
    ("skip is not a list", {"passed": True, "skip": 3}),
    ("skip holds a bool", {"passed": True, "skip": [True]}),
    ("skip holds a text", {"passed": True, "skip": ["2"]}),
    ("skip given", {"rule": "later", "passed": True, "skip": [3, 2]}),
]
RULES_FILES = {         # files that rulebook.load refuses, and their text; None: no file (folder.py is a folder)
    "absent.py": None,
    "folder.py": None,
    "broken.py": "def before_job(job, state:\n",
    "raises.py": "raise RuntimeError('not ready')\n",
}


def raises(job, state):
    raise ValueError("the hook of the experiment broke")


HOOKS = {               # a user's before_job hook in each form; its rule lines and exit code are in the golden
    "answer_5": lambda job, state: 5,
    "skip_not_a_list": lambda job, state: {"passed": True, "skip": 3},
    "raises": raises,
    "own_keys": lambda job, state: {"zeta": 1, "passed": True, "rule": "mine", "machine": "theirs", "alpha": [2]},
}


def rule_rows(places, point: str) -> str:
    """The rule lines of one point in the record of the test, as they are on disk."""
    rows = []
    for row in records_of(places)[0].read_text(encoding="utf-8").splitlines():
        line = json.loads(row)
        if line["event"] == "rule" and line["point"] == point:
            rows.append(f"{row}\n")
    return "".join(rows)


def test_each_generic_rule_on_a_table_of_inputs(golden):
    golden("units_rules_generic", "".join(f"{case}: {rule(*args)!r}\n" for case, rule, args in GENERIC))


def test_a_verdict_in_the_fixed_form(golden):
    golden("units_rules_checked", "".join(f"{case}: {rules.checked(raw, 'before_job')!r}\n" for case, raw in CHECKED))


def test_each_refusal_of_a_rules_file(golden, tmp_path):
    (tmp_path / "folder.py").mkdir()
    lines = []
    for name, text in RULES_FILES.items():
        if text is not None:
            (tmp_path / name).write_text(text)
        with pytest.raises(rulebook.RuleFileError) as caught:
            rulebook.load(tmp_path / name)
        lines.append(f"{name}: {caught.value}\n")
    golden("units_rules_file_refusals", "".join(lines))


@pytest.mark.parametrize("case", HOOKS)
def test_a_users_before_job_hook_in_each_form(tmp_path, places, clock, golden, case):
    code = send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1,
                user_rules={"before_job": HOOKS[case]})
    golden(f"units_rules_user_{case}", f"exit {code}\n" + rule_rows(places, "before_job"))


@pytest.mark.parametrize("user, code, named", [(True, 0, ["go_on"]), (False, 2, ["refusal"])])
def test_a_users_on_refusal_replaces_the_generic_rule(tmp_path, places, clock, user, code, named):
    hooks = {"on_refusal": lambda job, info: {"rule": "go_on", "passed": True}} if user else {}
    site = FakeSite(submits={1: ("refuse", 400)})
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, user_rules=hooks) == code
    lines = lines_of(records_of(places)[0])
    assert [e["rule"] for e in lines if e["event"] == "rule" and e["point"] == "on_refusal"] == named


def test_what_the_hooks_of_a_user_get_at_a_job_and_at_its_result(tmp_path, places, clock, golden):
    seen = []

    def before_job(job, state):
        seen.extend([("before_job job", job), ("before_job state", state)])
        return {"rule": "look", "passed": True}

    def after_result(job, result, state):
        seen.extend([("after_result job", job), ("after_result result", result), ("after_result state", state)])
        return {"rule": "look", "passed": True}

    hooks = {"before_job": before_job, "after_result": after_result}
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1, user_rules=hooks) == 0
    assert [len(value) for name, value in seen if name.endswith("state")] == [18, 18]
    golden("units_rules_hook_arguments", "".join(f"{name}: {json.dumps(value)}\n" for name, value in seen))


def refused(m, places, clock, hooks) -> int:
    return send(m, FakeSite(submits={1: ("refuse", 400)}), places, clock, max_order=1, user_rules=hooks)


def failed(m, places, clock, hooks) -> int:
    site = FakeSite(states={"J-1": [STATE("FAILED", final=True)]})
    return send(m, site, places, clock, max_order=1, user_rules=hooks)


def not_submitted(m, places, clock, hooks) -> int:
    """A VLQ-shaped order interrupted after its job was created, then collected while the site shows it configuring."""
    first = FakeSite("vlq", seconds_left=3600, submits={1: ("steps", ("interrupt",), [("created", {"job": 7})])})
    assert send(m, first, places, clock, max_order=1) == 130
    later = FakeSite("vlq", seconds_left=3600, states={7: [STATE("Configuring", configuring=True)]})
    return send(m, later, places, clock, resume=records_of(places)[0], user_rules=hooks)


@pytest.mark.parametrize("call, site", [(refused, "euroqexa"), (failed, "euroqexa"), (not_submitted, "vlq")])
def test_the_job_and_the_info_a_users_on_refusal_gets(tmp_path, places, clock, golden, call, site):
    seen = []

    def on_refusal(job, info):
        seen.append({"job": job, "info": info})
        return {"rule": "go_on", "passed": True}

    assert call(write_manifest(tmp_path / "m", site=site), places, clock, {"on_refusal": on_refusal}) == 0
    golden(f"units_rules_on_refusal_{call.__name__}", "".join(f"{json.dumps(entry)}\n" for entry in seen))
