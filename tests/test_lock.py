"""One live call per site at a time."""

import errno
import json
import os

import pytest
from fakes import TOKEN, FakeSite, cfg, records_of, send, write_manifest

from qdevices import check, lock, record, runner


def test_a_second_lock_on_the_same_site_is_refused(places):
    release = lock.Locks(places.state, host="h").take("vlq")
    with pytest.raises(lock.LockRefused, match="another live call"):
        lock.Locks(places.state, host="h").take("vlq")
    lock.Locks(places.state, host="h").take("euroqexa")()      # another site is free
    release()
    lock.Locks(places.state, host="h").take("vlq")()


def test_a_holder_of_another_host_refuses_although_the_flock_succeeds(places):
    places.state.mkdir(parents=True)
    (places.state / "vlq.holder").write_text(json.dumps({"host": "login-node-2", "pid": 1}))
    with pytest.raises(lock.LockRefused, match="login-node-2"):
        lock.Locks(places.state, host="login-node-1").take("vlq")


def test_a_holder_of_this_host_with_a_dead_pid_is_cleared(places):
    places.state.mkdir(parents=True)
    (places.state / "vlq.holder").write_text(json.dumps({"host": "h", "pid": 2 ** 22 + 12345}))
    release = lock.Locks(places.state, host="h").take("vlq")
    assert json.loads((places.state / "vlq.holder").read_text())["pid"] == os.getpid()
    release()
    assert not (places.state / "vlq.holder").exists()


def test_a_holder_of_this_host_with_a_live_pid_is_not_cleared(places):
    places.state.mkdir(parents=True)
    (places.state / "vlq.holder").write_text(json.dumps({"host": "h", "pid": os.getppid()}))
    with pytest.raises(lock.LockRefused, match="live process"):
        lock.Locks(places.state, host="h").take("vlq")


def test_unlock_refuses_a_wrong_host_name_and_clears_the_right_one(places):
    places.state.mkdir(parents=True)
    holder = places.state / "piastq.holder"
    holder.write_text(json.dumps({"host": "far", "pid": 99}))
    with pytest.raises(lock.LockRefused, match="not 'near'"):
        lock.Locks(places.state, host="here").unlock("piastq", "near")
    lines = []
    assert "removed" in lock.Locks(places.state, host="here").unlock("piastq", "far", write_line=lines.append)
    assert not holder.exists() and lines[0]["holder"]["host"] == "far"


def test_unlock_refuses_a_holder_of_this_host_that_is_alive(places):
    places.state.mkdir(parents=True)
    (places.state / "vlq.holder").write_text(json.dumps({"host": "here", "pid": os.getppid()}))
    with pytest.raises(lock.LockRefused, match="live process"):
        lock.Locks(places.state, host="here").unlock("vlq", "here")


def test_a_file_system_with_no_flock_refuses_the_live_call(places):
    def no_flock(fd, how):
        raise OSError(errno.ENOLCK, "No locks available")

    with pytest.raises(lock.LockRefused, match="no lock"):
        lock.Locks(places.state, host="h", flock=no_flock).take("vlq")


def test_a_holder_file_that_cannot_be_made_refuses_the_live_call(places, monkeypatch):
    real = os.open

    def refuse(path, flags, *a):
        if str(path).endswith(".holder"):
            raise PermissionError(errno.EACCES, "Permission denied")
        return real(path, flags, *a)

    monkeypatch.setattr(lock.os, "open", refuse)
    with pytest.raises(lock.LockRefused, match="cannot be made"):
        lock.Locks(places.state, host="h").take("vlq")


def test_the_lock_is_taken_before_any_record_is_read(tmp_path, places, clock, monkeypatch):
    m = write_manifest(tmp_path / "m")
    send(m, FakeSite(), places, clock, max_order=1)
    order = []
    real = record.RecordLines.read
    monkeypatch.setattr(record.RecordLines, "read", lambda p: (order.append("read"), real(p))[1])

    def take(name):
        order.append("lock")
        return lambda: order.append("release")

    send(m, FakeSite(), places, clock, resume=records_of(places)[0], max_order=2, take_lock=take)
    assert order[0] == "lock" and "read" in order and order[-1] == "release"


def test_a_send_is_refused_while_the_lock_is_held(tmp_path, places, clock):
    release = lock.Locks(places.state, host="host-a").take("euroqexa")
    site = FakeSite()
    with pytest.raises(runner.Refused, match="another live call"):
        send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1)
    assert site.calls == []
    release()


def test_check_live_is_refused_while_the_lock_is_held(places, clock):
    release = lock.Locks(places.state, host="host-a").take("piastq")
    made = []
    with pytest.raises(runner.Refused, match="another live call"):
        check.check("piastq", live=True, token=TOKEN, manifest_path=None, cfg=cfg(), places=places, clock=clock,
                    sleep=clock.sleep, host="host-a", make_site=lambda *a, **k: made.append(1),
                    say=lambda *a, **k: None)
    assert made == []
    release()
