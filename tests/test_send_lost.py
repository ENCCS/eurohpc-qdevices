"""The send loop with a fake site: an unknown answer, a lost order, `resolve`, and an error of the program."""

import pytest
from fakes import FakeSite, events, lines_of, records_of, send, write_manifest

from qdevices import runner
from qdevices.ledger import Ledger
from qdevices.resolve import resolve


@pytest.mark.parametrize("action", [("unknown", 500), ("unknown", 503), ("unknown", 307), ("noanswer",), ("noid",)])
def test_an_unknown_answer_stops_and_the_order_is_never_sent_again(tmp_path, places, clock, action):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(submits={1: action}), places, clock, max_order=3) == 2
    rec = records_of(places)[0]
    assert events(rec, "stop")[-1]["kind"] == "unknown"
    assert Ledger(lines_of(rec)).orders[1].status == "lost"
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, max_order=3) == 1      # lost: refused to go on
    assert not [c for c in site.calls if c[0] in ("submit", "prepare")]
    assert events(rec, "stop")[-1]["kind"] == "lost"


def test_a_lost_order_blocks_a_new_run_until_resolved_none(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(submits={1: ("noanswer",)}), places, clock, max_order=1)
    rec = records_of(places)[0]
    clock.t += 5
    with pytest.raises(runner.Refused, match="open or lost"):
        send(m, FakeSite(), places, clock, max_order=1, new_run=True)
    other = write_manifest(tmp_path / "other")
    with pytest.raises(runner.Refused, match="open or lost"):
        send(other, FakeSite(), places, clock, max_order=1)          # a first start of another run too
    resolve(rec, 1, None, places=places, clock=clock, host="host-a")
    assert Ledger(lines_of(rec)).orders[1].final == "resolved_none"
    assert send(m, FakeSite(), places, clock, max_order=1, new_run=True) == 0


def test_resolve_with_a_job_id_lets_a_resume_collect_it(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(submits={1: ("interrupt",)}), places, clock, max_order=1)
    rec = records_of(places)[0]
    resolve(rec, 1, "J-found", places=places, clock=clock, host="host-a")
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec) == 0
    assert ("status", "J-found") in site.calls and not [c for c in site.calls if c[0] == "submit"]
    assert events(rec, "result")[0]["id"] == "J-found"


def test_resolve_refuses_an_order_that_is_not_lost(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    rec = records_of(places)[0]
    for order in (1, 2):
        with pytest.raises(runner.Refused, match="not lost"):
            resolve(rec, order, None, places=places, clock=clock, host="host-a")


def test_exit_code_3_for_an_error_of_the_program(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    site = FakeSite(submits={1: ("crash",)})
    assert send(m, site, places, clock, max_order=1) == 3
    rec = records_of(places)[0]
    assert events(rec, "stop")[-1]["kind"] == "error"
    assert Ledger(lines_of(rec)).orders[1].status == "lost"


def test_exit_code_3_for_an_error_in_a_wait(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    site = FakeSite(states={"J-1": [TypeError("bad")]})
    assert send(m, site, places, clock, max_order=1) == 3
    assert Ledger(lines_of(records_of(places)[0])).orders[1].status == "open"
