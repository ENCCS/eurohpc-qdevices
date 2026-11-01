"""Invariants 2 (never cancel), 9 (the screen never ends a call) and 10 (resume only from the record itself)."""

import io
import os
import shutil
import signal
import sys

import pytest
from fakes import STATE, FakeSite, lines_of, records_of, send, write_manifest

from qdevices import runner
from qdevices.ledger import Ledger
from qdevices.resolve import resolve
from qdevices.sites import SITES


def stop_kind(places):
    return [line for line in lines_of(records_of(places)[0]) if line["event"] == "stop"][-1]


@pytest.mark.parametrize("how", ["ctrl-c", "sigterm"])
def test_an_interrupt_in_a_wait_writes_a_stop_and_cancels_nothing(tmp_path, places, clock, how):
    def hit():
        if how == "ctrl-c":
            raise KeyboardInterrupt()
        os.kill(os.getpid(), signal.SIGTERM)
        return STATE()

    site = FakeSite(states={"J-1": [hit, STATE()]})
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 130
    line = stop_kind(places)
    assert line["kind"] == "interrupt" and line["id"] == "J-1"
    assert "nothing was cancelled" in line["reason"]
    assert Ledger(lines_of(records_of(places)[0])).orders[1].status == "open"


def test_an_interrupt_in_the_request_leaves_a_lost_order_that_is_never_sent_again(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(submits={1: ("interrupt",)}), places, clock, max_order=3) == 130
    rec = records_of(places)[0]
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, max_order=3) == 1
    assert not [c for c in site.calls if c[0] == "submit"]


def test_an_ignored_sighup_stays_ignored(tmp_path, places, clock):
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

    def hup():
        os.kill(os.getpid(), signal.SIGHUP)
        return STATE("COMPLETED", final=True, ok=True)

    site = FakeSite(states={"J-1": [hup]})
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 0
    assert signal.getsignal(signal.SIGHUP) == signal.SIG_IGN


def test_no_site_class_has_a_cancel_method():
    for cls in SITES.values():
        assert not [name for name in dir(cls) if "cancel" in name.lower()]


def test_a_closed_screen_does_not_end_a_call(tmp_path, places, clock, monkeypatch):
    closed = io.StringIO()
    closed.close()
    monkeypatch.setattr(sys, "stdout", closed)
    m = write_manifest(tmp_path / "m")
    code = runner.send(m, FakeSite(), cfg=__import__("fakes").cfg(), places=places, clock=clock, sleep=clock.sleep,
                       host="host-a", max_order=3)
    assert code == 0
    assert len([line for line in lines_of(records_of(places)[0]) if line["event"] == "result"]) == 3


def test_a_resume_from_a_copy_sends_nothing(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    rec = records_of(places)[0]
    copy = tmp_path / "elsewhere" / rec.name
    copy.parent.mkdir()
    shutil.copy(rec, copy)
    with pytest.raises(runner.Refused, match="copy"):
        send(m, FakeSite(), places, clock, resume=copy, max_order=2)
    site = FakeSite()
    assert send(m, site, places, clock, resume=copy) == 0             # collect only is allowed
    assert not [c for c in site.calls if c[0] == "submit"]


def test_a_record_whose_inode_differs_from_its_start_line_is_refused(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    rec = records_of(places)[0]
    other = tmp_path / "copy.jsonl"
    shutil.copy(rec, other)
    rec.unlink()
    shutil.move(other, rec)
    with pytest.raises(runner.Refused, match="inode"):
        send(m, FakeSite(), places, clock, resume=rec, max_order=2)


def test_a_resume_that_sends_takes_only_the_newest_record_of_its_run(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    old = records_of(places)[0]
    clock.t += 5
    send(m, FakeSite(), places, clock, max_order=1, new_run=True)
    with pytest.raises(runner.Refused, match="newest"):
        send(m, FakeSite(), places, clock, resume=old, max_order=2)


def test_a_resume_with_max_order_from_another_host_is_refused(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1, host="laptop")
    with pytest.raises(runner.Refused, match="host"):
        send(m, FakeSite(), places, clock, resume=records_of(places)[0], max_order=2, host="login-node")


@pytest.mark.parametrize("steps, code, final", [
    ([("created", {"job": 7})], 2, True),                                  # interrupted before the submit request
    ([("created", {"job": 7}), ("uploaded", {"job": 7})], 1, False),       # the submit request may have gone out
])
def test_an_interrupt_at_each_vlq_step_leaves_an_open_job_that_is_never_submitted_on_resume(
        tmp_path, places, clock, steps, code, final):
    m = write_manifest(tmp_path / "m", site="vlq")
    site = FakeSite("vlq", seconds_left=3600, submits={1: ("steps", ("interrupt",), steps)})
    assert send(m, site, places, clock, max_order=1) == 130
    rec = records_of(places)[0]
    assert stop_kind(places)["id"] == 7
    assert Ledger(lines_of(rec)).orders[1].status == "open"
    site = FakeSite("vlq", seconds_left=3600, states={7: [STATE("Configuring", configuring=True)]})
    assert send(m, site, places, clock, resume=rec) == code
    assert not [c for c in site.calls if c[0] in ("submit", "prepare")]
    not_submitted = [line for line in lines_of(rec) if line["event"] == "not_submitted"]
    if final:
        assert not_submitted[0]["id"] == 7
        assert Ledger(lines_of(rec)).orders[1].status == "final"
    else:
        assert not not_submitted and stop_kind(places)["kind"] == "submit_unknown"
        assert Ledger(lines_of(rec)).orders[1].status == "open"


def test_a_configuring_job_whose_record_has_no_made_line_stays_open(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="vlq")
    assert send(m, FakeSite("vlq", seconds_left=3600, submits={1: ("noanswer",)}), places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    resolve(rec, 1, "7", places=places, clock=clock, host="host-a")     # an id found at the site, no "created" line
    site = FakeSite("vlq", seconds_left=3600, states={7: [STATE("Configuring", configuring=True)]})
    assert send(m, site, places, clock, resume=rec) == 1
    assert not [c for c in site.calls if c[0] in ("submit", "prepare")]
    assert stop_kind(places)["kind"] == "submit_unknown"
    assert Ledger(lines_of(rec)).orders[1].status == "open"


def test_an_interrupt_in_the_init_job_leaves_the_order_unsent(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="vlq")
    site = FakeSite("vlq", seconds_left=3600)

    def prepare(job, note):
        note("init_submitting")
        note("init_created", init_job=5)
        raise KeyboardInterrupt()

    site.prepare = prepare
    assert send(m, site, places, clock, max_order=1) == 130
    lines = lines_of(records_of(places)[0])
    assert Ledger(lines).orders[1].status == "unsent"
    assert [line["step"] for line in lines if line["event"] == "init"] == ["init_submitting", "init_created"]
