"""The send loop with a fake site: refusals, failed jobs, skips, and the generic and user rules."""

from fakes import STATE, FakeSite, cfg, events, lines_of, records_of, send, write_manifest

from qdevices.ledger import Ledger


def test_each_refusal_is_final_and_stops_by_default(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(submits={1: ("refuse", 400)}), places, clock, max_order=3) == 2
    rec = records_of(places)[0]
    assert events(rec, "refused")[0]["http_status"] == 400
    assert Ledger(lines_of(rec)).orders[1].status == "final"


def test_a_users_on_refusal_can_let_the_run_go_on(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    user = {"on_refusal": lambda job, info: {"rule": "mine", "passed": True}}
    site = FakeSite(submits={2: ("refuse", 400)})
    assert send(m, site, places, clock, max_order=3, user_rules=user) == 0
    assert [c[1] for c in site.calls if c[0] == "submit"] == [1, 2, 3]


def test_a_failed_job_is_final_and_its_logs_are_filtered(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    site = FakeSite(states={"J-1": [STATE("FAILED", final=True)]})
    assert send(m, site, places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    assert events(rec, "failed")[0]["state"] == "FAILED"
    assert site._token not in rec.read_text()


def test_a_skip_names_orders_that_are_then_never_sent(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    user = {"after_result": lambda job, result, state: {"rule": "S", "passed": True,
                                                        "skip": [2] if job["order"] == 1 else []}}
    site = FakeSite()
    assert send(m, site, places, clock, max_order=3, user_rules=user) == 0
    assert [c[1] for c in site.calls if c[0] == "submit"] == [1, 3]
    assert events(records_of(places)[0], "skip")[0]["orders"] == [2]


def test_a_skip_of_an_order_that_was_sent_stops(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    user = {"after_result": lambda job, result, state: {"rule": "S", "passed": True, "skip": [1]}}
    assert send(m, FakeSite(), places, clock, max_order=3, user_rules=user) == 2


def test_a_hook_that_raises_stops_with_exit_code_2(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")

    def broken(job, state):
        raise ValueError("no")

    site = FakeSite()
    assert send(m, site, places, clock, max_order=1, user_rules={"before_job": broken}) == 2
    assert not [c for c in site.calls if c[0] == "submit"]


def test_the_shot_limit_of_the_site_stops_before_the_request(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 300),))
    site = FakeSite(max_shots=200)
    assert send(m, site, places, clock, max_order=1) == 2
    assert not [c for c in site.calls if c[0] == "submit"]


def test_the_vlq_token_rule_refuses_a_job_with_less_than_30_minutes(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="vlq")
    site = FakeSite("vlq", seconds_left=29 * 60)
    assert send(m, site, places, clock, max_order=1) == 2
    assert not [c for c in site.calls if c[0] in ("submit", "prepare")]
    clock.t += 5
    assert send(m, FakeSite("vlq", seconds_left=31 * 60), places, clock, max_order=1) == 0


def test_the_budget_counts_all_records_and_stops_before_the_job(tmp_path, places, clock):
    conf = cfg().copy()
    conf["euroqexa"] = {**conf["euroqexa"], "budget_seconds": 101.0}
    m = write_manifest(tmp_path / "m")
    site = FakeSite()
    assert send(m, site, places, clock, conf, max_order=3) == 2       # 1.5 s used, 1.5 + 100 > 101 at order 2
    assert [c[1] for c in site.calls if c[0] == "submit"] == [1]


def test_a_lost_order_counts_at_the_job_time_limit():
    lines = [{"event": "submitting", "order": 1, "name": "J1"},
             {"event": "submitting", "order": 2, "name": "J2"}, {"event": "submitted", "order": 2, "id": "x"},
             {"event": "result", "order": 2, "id": "x", "seconds": 2.0}]
    assert Ledger(lines).used_seconds(100.0) == 102.0
    lines.append({"event": "resolved", "order": 1, "none": True})
    assert Ledger(lines).used_seconds(100.0) == 2.0


def test_the_config_can_replace_the_piastq_shot_limit(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 300),))
    assert send(m, FakeSite("piastq", max_shots=200), places, clock, max_order=1) == 2      # 200 holds by default
    conf = cfg().copy()
    conf["piastq"] = {**conf["piastq"], "site_max_shots": 400}
    site = FakeSite("piastq", max_shots=200)
    m2 = write_manifest(tmp_path / "m2", site="piastq", jobs=(("J1", 300),))
    assert send(m2, site, places, clock, conf, max_order=1) == 0                             # the site then decides
    assert [c[1] for c in site.calls if c[0] == "submit"] == [1]
