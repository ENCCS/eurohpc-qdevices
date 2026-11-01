"""An order whose job id no URL can hold may have a job: `resolve --none` makes it final at the job time limit."""

import httpx
from fakes import eqe, lines_of, records_of
from test_site_answers import eqe_text, portal

from qdevices.ledger import Ledger
from qdevices.resolve import resolve

STUCK = ("order 1 is final: the site gave a job id that no URL can hold, so a job may exist; it is not cancelled, "
         "and it counts at the job time limit")


def test_none_on_an_order_lost_by_an_id_no_url_holds_counts_at_the_job_time_limit(tmp_path, places, clock):
    m = eqe.manifest(tmp_path / "m", eqe_text())
    code, lines = eqe.send(m, portal([], job=httpx.Response(200, json={"uuid": "u\n1"})), places, clock, max_order=1)
    assert code == 2 and lines[-1]["id_no_url"] is True
    rec = records_of(places)[0]
    assert resolve(rec, 1, None, places=places, clock=clock, host="h") == STUCK
    resolved = lines_of(rec)[-1]
    assert (resolved["none"], resolved["stuck"]) == (True, True)
    order = Ledger(lines_of(rec)).orders[1]
    assert (order.final, order.budget(100.0)) == ("resolved_stuck", 100.0)


def test_none_on_a_lost_order_with_no_answer_still_counts_0(tmp_path, places, clock):
    m = eqe.manifest(tmp_path / "m", eqe_text())
    code, lines = eqe.send(m, portal([], job=httpx.Response(200, json={})), places, clock, max_order=1)
    assert code == 2 and "id_no_url" not in lines[-1]
    rec = records_of(places)[0]
    assert resolve(rec, 1, None, places=places, clock=clock, host="h") == "order 1 is final with no job"
    assert Ledger(lines_of(rec)).orders[1].budget(100.0) == 0.0
