"""Invariant 1 on VLQ: a job made and not seen as submitted is never submitted on a resume."""

import pytest
from fakes import lines_of, records_of
from fakes.vlq import creates, go, make_vlq, submits

from qdevices import runner
from qdevices.ledger import Ledger
from qdevices.resolve import resolve


def test_submit_never_sent_and_configuring_on_resume_is_final_not_submitted(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path, fail={("upload", 102): 500})   # 101 init job, 102 metered
    assert go(m, site, places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    assert lines_of(rec)[-1]["kind"] == "unknown" and lines_of(rec)[-1]["id"] == 102
    assert "uploaded" not in [e.get("step") for e in lines_of(rec)]     # SubmitJob was never sent
    fake.states[102] = [1]                                 # Configuring
    before = len(submits(fake))
    assert go(m, site, places, clock, resume=rec) == 2     # final, and the generic rule stops at it
    assert len(submits(fake)) == before                    # SubmitJob is never called on a resume
    assert next(e for e in lines_of(rec) if e["event"] == "not_submitted")["id"] == 102
    assert Ledger(lines_of(rec)).orders[1].status == "final"


@pytest.mark.parametrize("fail", [{("submit", 102): 400}, {("submit", 102): 503}])
def test_submit_sent_with_no_good_answer_and_configuring_on_resume_stays_open(tmp_path, fail):
    places, clock, fake, m, site = make_vlq(tmp_path, fail=fail)
    assert go(m, site, places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    assert "uploaded" in [e.get("step") for e in lines_of(rec)]         # SubmitJob was sent
    assert not [e for e in lines_of(rec) if e["event"] == "submitted"]
    fake.states[102] = [1]                                 # Configuring
    before = (len(creates(fake)), len(submits(fake)), len(fake.requests))
    assert go(m, site, places, clock, resume=rec) == 1
    assert (len(creates(fake)), len(submits(fake))) == before[:2]      # nothing made and nothing sent
    assert all(r[0] == "GET" for r in fake.requests[before[2]:])       # reads only
    lines = lines_of(rec)
    assert not [e for e in lines if e["event"] == "not_submitted"]
    assert lines[-1]["event"] == "stop" and lines[-1]["kind"] == "submit_unknown" and lines[-1]["id"] == 102
    assert Ledger(lines).orders[1].status == "open"
    with pytest.raises(runner.Refused, match="open or lost"):           # it blocks a new run
        go(m, site, places, clock, max_order=1, new_run=True)
    with pytest.raises(runner.Refused, match="has the job 102 already"):
        resolve(rec, 1, "102", places=places, clock=clock, host="h")
    resolve(rec, 1, None, places=places, clock=clock, host="h")         # the site showed that it never ran
    assert Ledger(lines_of(rec)).orders[1].final == "resolved_none"
    assert len(submits(fake)) == before[1]


def test_a_created_job_found_queued_on_resume_is_collected(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path, fail={("submit", 102): 503})
    assert go(m, site, places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    fake.states[102] = [4, 16]                             # Queued, then Finished: the submission had gone through
    before = len(submits(fake))
    assert go(m, site, places, clock, resume=rec) == 0
    assert len(submits(fake)) == before
    assert next(e for e in lines_of(rec) if e["event"] == "result")["id"] == 102


def test_with_no_state_the_resume_stops_with_exit_code_1(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path, states={102: [8]})
    assert go(m, site, places, clock, max_order=1) == 2    # the wait time-out leaves the job open
    rec = records_of(places)[0]
    fake.states[102] = [None]
    assert go(m, site, places, clock, resume=rec) == 1
    assert Ledger(lines_of(rec)).orders[1].status == "open"


def test_collect_only_makes_no_job_of_any_kind(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path, states={102: [8]})
    go(m, site, places, clock, max_order=1)
    rec = records_of(places)[0]
    before = len(creates(fake))
    fake.states[102] = [16]
    assert go(m, site, places, clock, resume=rec) == 0
    assert len(creates(fake)) == before and not [r for r in fake.requests[-6:] if r[1].endswith("SubmitJob")]
