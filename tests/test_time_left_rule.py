"""The VLQ token rule: max(30 minutes, 2 x wait_seconds) left before each job, as the init job and the job each wait."""

import pytest
from fakes import FakeSite, cfg, events, records_of, send, write_manifest

from qdevices import config, rules

NO_WAIT = """
[vlq]
projects = ["TEST-PROJECT"]
lexis_projects = ["TEST-LEXIS"]
budget_seconds = 1000
job_seconds_limit = 100
"""


def token(minutes: int, **state) -> dict:
    return rules.token_time({}, {"site": "vlq", "token_seconds_left": minutes * 60.0, **state})


@pytest.mark.parametrize("minutes, passed", [(59, False), (60, True)])
def test_with_wait_seconds_1800_the_token_needs_60_minutes(minutes, passed):
    verdict = token(minutes, wait_seconds=1800.0)
    assert verdict["passed"] is passed and verdict["minutes_needed"] == 60
    assert verdict["reason"] == (None if passed else "the token has 59 minutes left, fewer than 60")


@pytest.mark.parametrize("state", [{"wait_seconds": config.parse(NO_WAIT)["vlq"]["wait_seconds"]}, {}])
def test_by_default_the_token_needs_30_minutes(state):
    assert config.parse(NO_WAIT)["vlq"]["wait_seconds"] == 900
    assert token(30, **state)["passed"] is True
    refused = token(29, **state)
    assert refused["passed"] is False and refused["reason"] == "the token has 29 minutes left, fewer than 30"


def test_the_minutes_needed_are_rounded_up():
    verdict = token(33, wait_seconds=1000.0)              # 2000 s needed: 33 minutes 20 seconds
    assert verdict["passed"] is False and verdict["reason"] == "the token has 33 minutes left, fewer than 34"
    assert token(34, wait_seconds=1000.0)["passed"] is True


def test_a_send_takes_wait_seconds_from_the_config(tmp_path, places, clock):
    conf = cfg()
    conf["vlq"] = {**conf["vlq"], "wait_seconds": 1800}
    m = write_manifest(tmp_path / "m", site="vlq")
    seen = []
    user = {"before_job": lambda job, state: seen.append(state["wait_seconds"]) or {"passed": True}}
    site = FakeSite("vlq", seconds_left=59 * 60)
    assert send(m, site, places, clock, conf, max_order=1, user_rules=user) == 2
    assert not [c for c in site.calls if c[0] in ("submit", "prepare")]
    rule = next(e for e in events(records_of(places)[0], "rule") if e["rule"] == "token")
    assert rule["passed"] is False and rule["minutes_needed"] == 60 and seen == [1800.0]
    clock.t += 5
    assert send(m, FakeSite("vlq", seconds_left=60 * 60), places, clock, conf, max_order=1) == 0
