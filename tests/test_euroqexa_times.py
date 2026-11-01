"""The time stamps of Euro-Q-Exa: Central European time by the written rule, the repeated hour, the check."""

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fakes import QASM, FakeClock, cfg, places_in, records_of
from fakes.eqe import STAMPS, Portal, manifest, send, site

from qdevices.resolve import resolve
from qdevices.sites import local_time

HOUR = timedelta(hours=1)
KEYS = ("timestamp_submitted", "timestamp_scheduled", "timestamp_completed")


def result(stamps, submitted_utc) -> dict:
    """The result of job u-1 with these three stamps, after the app gave its own submitted_utc."""
    eqe = site(Portal(1, [(0, 1)], [], stamps=dict(zip(KEYS, stamps, strict=True))))
    if submitted_utc is not None:
        eqe.sent_at("u-1", submitted_utc)
    try:
        return eqe.result("u-1")
    finally:
        eqe.close()


def test_the_offset_changes_at_0100_utc_on_the_last_sundays_of_march_and_october():
    assert local_time.offset(datetime(2027, 3, 28, 0, 59, 59, tzinfo=UTC)) == HOUR
    assert local_time.offset(datetime(2027, 3, 28, 1, 0, tzinfo=UTC)) == 2 * HOUR
    assert local_time.offset(datetime(2027, 10, 31, 0, 59, 59, tzinfo=UTC)) == 2 * HOUR
    assert local_time.offset(datetime(2027, 10, 31, 1, 0, tzinfo=UTC)) == HOUR
    assert local_time.readings("2027-03-28 02:30:00") == []                  # the hour the March change skips
    assert len(local_time.readings("2027-10-31 02:30:00")) == 2              # the hour the October change repeats


def test_a_job_across_the_october_change_takes_the_reading_of_its_submission():
    out = result(("2027-10-31 02:58:29", "2027-10-31 02:59:00", "2027-10-31 02:01:00"), "2027-10-31T00:58:30Z")
    assert out["seconds"] == 120.0 and out["zone_check"] is True
    assert out["scheduled_utc"] == "2027-10-31T00:59:00+00:00" and out["completed_utc"] == "2027-10-31T01:01:00+00:00"
    assert out["timestamp_completed"] == "2027-10-31 02:01:00"               # the stamps of the site stay


@pytest.mark.parametrize("completed, plain", [("2027-10-31 02:45:00", 300.0), ("2027-10-31 03:10:00", 1800.0)],
                         ids=["completed-in-the-repeated-hour", "scheduled-in-the-repeated-hour"])
def test_stamps_that_can_be_read_two_ways_give_no_zone_check(completed, plain):
    out = result(("2027-10-31 02:39:00", "2027-10-31 02:40:00", completed), "2027-10-31T00:39:00Z")
    assert out["zone_check"] is False and out["seconds"] == plain
    assert out["scheduled_utc"] is None and out["completed_utc"] is None


@pytest.mark.parametrize("submitted_utc, stamps, scheduled_utc", [
    ("2027-10-20T12:00:00+00:00", ("2027-10-20 14:00:00", "2027-10-20 14:00:04", "2027-10-20 14:00:16"),
     "2027-10-20T12:00:04+00:00"),
    ("2027-10-31T19:00:00+00:00", ("2027-10-31 20:00:00", "2027-10-31 20:00:04", "2027-10-31 20:00:16"),
     "2027-10-31T19:00:04+00:00"),
], ids=["summer-time-two-hours", "evening-after-the-change-one-hour"])
def test_stamps_are_two_hours_ahead_in_summer_time_and_one_after_the_change(submitted_utc, stamps, scheduled_utc):
    out = result(stamps, submitted_utc)
    assert out["scheduled_utc"] == scheduled_utc and out["seconds"] == 12.0 and out["zone_check"] is True


def test_stamps_that_do_not_agree_with_submitted_utc_keep_the_plain_interval():
    out = result(("2027-10-20 12:00:00", "2027-10-20 12:00:05", "2027-10-20 12:00:15"), "2027-10-20T12:00:00+00:00")
    assert out["zone_check"] is False and out["seconds"] == 10.0 and out["scheduled_utc"] is None
    assert result(("2027-10-20 14:00:00", "2027-10-20 14:00:05", "2027-10-20 14:00:15"), None)["zone_check"] is False


def test_a_bad_stamp_gives_no_seconds():
    out = result(("2027-10-20 14:00:00", "not a time", "2027-10-20 14:00:15"), "2027-10-20T12:00:00+00:00")
    assert out["seconds"] is None and out["zone_check"] is False


def test_a_send_reads_the_stamps_against_its_own_submitted_utc(tmp_path):
    code, lines = send(manifest(tmp_path / "m", QASM), Portal(1, [(0, 1)], []), places_in(tmp_path), FakeClock(),
                       max_order=1)
    found = next(e for e in lines if e["event"] == "result")
    assert code == 0 and found["zone_check"] is True and found["seconds"] == 2.0
    assert found["completed_utc"] == "2026-01-05T12:00:03+00:00"


def test_a_resume_reads_the_stamps_against_the_submitted_utc_of_the_record(tmp_path):
    places, clock = places_in(tmp_path), FakeClock()
    path = manifest(tmp_path / "m", QASM)
    code, lines = send(path, Portal(1, [(0, 1)], [], states=("WAITING",)), places, clock, max_order=1)
    assert code == 2 and lines[-1]["kind"] == "timeout"
    code, lines = send(path, Portal(1, [(0, 1)], []), places, clock, resume=records_of(places)[0])
    found = next(e for e in lines if e["event"] == "result")
    assert code == 0 and found["zone_check"] is True and found["scheduled_utc"] == "2026-01-05T12:00:01+00:00"
    assert found["timestamp_scheduled"] == "2026-01-05 13:00:01"


def test_a_lost_order_given_its_id_reads_the_stamps_against_its_submitting_line(tmp_path):
    places, clock, path = places_in(tmp_path), FakeClock(), manifest(tmp_path / "m", QASM)
    clock.start = datetime(2027, 10, 31, 0, 58, 30, tzinfo=UTC)     # the job request, 90 s before the October change
    across = Portal(1, [(0, 1)], [], stamps=dict(zip(KEYS, ("2027-10-31 02:58:29", "2027-10-31 02:59:00",
                                                           "2027-10-31 02:01:00"), strict=True)))
    code, lines = send(path, lambda request: httpx.Response(500) if request.method == "POST" else across(request),
                       places, clock, max_order=1)
    assert code == 2 and lines[-1]["kind"] == "unknown"                     # lost: a 'submitting' line and no id
    resolve(records_of(places)[0], 1, "u-1", places=places, clock=clock, host="h")
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "job_seconds_limit": 300.0}
    code, lines = send(path, across, places, clock, conf, resume=records_of(places)[0])
    found = next(e for e in lines if e["event"] == "result")
    assert not any(e["event"] == "submitted" for e in lines)
    assert code == 0 and found["zone_check"] is True and found["seconds"] == 120.0


def test_a_stamp_outside_the_calendar_in_utc_keeps_the_plain_interval_and_a_rule_stops(tmp_path):
    placeholder = {**STAMPS, "timestamp_scheduled": "0001-01-01 00:00:00"}
    code, lines = send(manifest(tmp_path / "m", QASM), Portal(1, [(0, 1)], [], stamps=placeholder),
                       places_in(tmp_path), FakeClock(), max_order=1)
    found = next(e for e in lines if e["event"] == "result")
    assert found["zone_check"] is False
    assert found["seconds"] == (datetime(2026, 1, 5, 13, 0, 3) - datetime(1, 1, 1)).total_seconds()
    assert code == 2 and lines[-1]["kind"] == "rule" and lines[-1]["rule"] == "job_time"     # not 3, an error
    assert local_time.readings("0001-01-01 00:00:00") == local_time.readings("0001-01-01T00:30:00+01:00") == []
