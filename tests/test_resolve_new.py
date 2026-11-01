"""`resolve --none` on an open order that the site showed only as New for days: final, not cancelled, counted."""

import pytest
from fakes import STATE, FakeSite, events, lines_of, records_of, send, write_manifest

from qdevices import runner
from qdevices.ledger import Ledger
from qdevices.resolve import resolve

DAY = 86400.0


def new_site(state="New"):
    return FakeSite(states={"J-1": [STATE(state)]})


def sent_new(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(m, new_site(), places, clock, max_order=1) == 2     # still New at the end of the wait
    return m, records_of(places)[0]


def test_an_order_new_for_days_is_resolved_none_and_counts_at_the_limit(tmp_path, places, clock):
    m, rec = sent_new(tmp_path, places, clock)
    clock.t += 4 * DAY
    assert send(m, new_site(), places, clock, resume=rec) == 2      # read again on the day: still New
    assert "not cancelled" in resolve(rec, 1, None, places=places, clock=clock, host="host-a")
    assert events(rec, "resolved")[-1]["still_new"] is True
    lines = lines_of(rec)
    assert Ledger(lines).orders[1].final == "resolved_new"
    assert Ledger(lines).used_seconds(100.0) == 100.0                 # at the job time limit, not 0
    other = write_manifest(tmp_path / "other", jobs=(("J1", 10),))
    assert send(other, FakeSite(), places, clock, max_order=1) == 0   # the site takes a new run again


def test_still_new_is_refused_too_soon_without_a_read_of_the_day_with_an_id_or_once_seen_queued(
        tmp_path, places, clock):
    m, rec = sent_new(tmp_path, places, clock)
    with pytest.raises(runner.Refused, match="less than 3 days"):
        resolve(rec, 1, None, places=places, clock=clock, host="host-a")
    clock.t += 4 * DAY
    with pytest.raises(runner.Refused, match="read it once more"):
        resolve(rec, 1, None, places=places, clock=clock, host="host-a")
    send(m, new_site(), places, clock, resume=rec)
    with pytest.raises(runner.Refused, match="only --none"):
        resolve(rec, 1, "J-1", places=places, clock=clock, host="host-a")
    send(m, new_site("Queued"), places, clock, resume=rec)
    with pytest.raises(runner.Refused, match="showed it as Queued"):
        resolve(rec, 1, None, places=places, clock=clock, host="host-a")
    assert Ledger(lines_of(rec)).orders[1].status == "open"
