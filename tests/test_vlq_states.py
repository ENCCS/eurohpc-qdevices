"""The HEAppE job states of VLQ: their names, the states that end a wait, Deleted as a failure, a failed init job."""

import pytest
from fakes import events, lines_of, records_of
from fakes.vlq import creates, go, make_vlq, submits

from qdevices.sites.vlq.wire import STATES, HeappeState

DOCUMENTED = {1: "Configuring", 2: "Submitted", 4: "Queued", 8: "Running", 16: "Finished", 32: "Failed",
              64: "Canceled", 128: "WaitingForServiceAccount", 256: "Deleted"}
INIT_ENDS = {            # the states the init job 101 reports, then the step and the error of the stop
    "failed": ([32], "init_failed", "init job 101 ended Failed; no metered job was made"),
    "still_running": ([8], "init_wait", "init job 101 still Running after 60 s; it is not cancelled"),
}


def test_each_documented_state_has_its_name():
    assert STATES == DOCUMENTED
    assert HeappeState.of(256).name == "Deleted"
    assert HeappeState.of(512).name == "unknown(512)"


def test_deleted_ends_the_wait_and_waiting_for_a_service_account_does_not():
    assert HeappeState.of(256).final and HeappeState.of(16).final and HeappeState.of(512).final
    assert not HeappeState.of(128).final and not HeappeState.of(8).final


@pytest.mark.parametrize("case", list(INIT_ENDS))
def test_an_init_job_that_fails_or_is_still_running_at_wait_seconds_stops_the_order_before_its_metered_job(
        tmp_path, case):
    states, step, error = INIT_ENDS[case]
    places, clock, fake, m, site = make_vlq(tmp_path, states={101: states})
    assert go(m, site, places, clock, max_order=1) == 1
    last = lines_of(records_of(places)[0])[-1]
    assert (last["event"], last["kind"], last["step"], last["error"]) == ("stop", "prepare", step, error)
    assert len(creates(fake)) == 1 and len(submits(fake)) == 1        # the init job only: no metered job is made


def test_the_site_reads_a_deleted_job_as_final_and_not_a_success(tmp_path):
    _places, _clock, _fake, _m, site = make_vlq(tmp_path, states={7: [256]})
    state = site.status(7)
    assert {key: state[key] for key in ("state", "final", "ok", "code")} == {
        "state": "Deleted", "final": True, "ok": False, "code": 256}


def test_a_metered_job_shown_as_deleted_is_a_failed_job_by_its_name(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path, states={102: [256]})
    assert go(m, site, places, clock, max_order=2) == 2
    rec = records_of(places)[0]
    assert events(rec, "failed")[0]["state"] == "Deleted"
    assert "unknown(256)" not in rec.read_text()
    assert len(submits(fake)) == 2          # the init job and the metered job of order 1; order 2 is not sent
