"""The lock of a site: every text of `take` and `unlock` whole, what `release` keeps, and `qdevices unlock`."""

import errno
import json
import os
from pathlib import Path

import pytest
from fakes import lines_of
from fakes.older import main

from qdevices import lock

DEAD = 2 ** 22 + 12345          # above the largest pid of Linux: no process has it
LIVE = {"host": "host-a", "pid": os.getpid()}
OPEN = os.open


def no_flock(fd, how):
    raise OSError(errno.ENOLCK, "No locks available")


def denied(path, flags, *a):
    """An os.open that may not make a holder file."""
    if str(path).endswith(".holder"):
        raise PermissionError(errno.EACCES, "Permission denied")
    return OPEN(path, flags, *a)


def racing(path, flags, *a):
    """An os.open at which another call has made the holder file again, each time this one would make it."""
    if str(path).endswith(".holder"):
        Path(path).write_text(json.dumps({"host": "host-a", "pid": DEAD}))
        raise FileExistsError(errno.EEXIST, "File exists", str(path))
    return OPEN(path, flags, *a)


def holder(state: Path, value) -> Path:
    """The holder file of vlq in `state`, with a JSON value, or a text as it is."""
    state.mkdir(parents=True, exist_ok=True)
    path = state / "vlq.holder"
    path.write_text(value if isinstance(value, str) else json.dumps(value))
    return path


def refused(action, *args, **kw) -> str:
    with pytest.raises(lock.LockRefused) as caught:
        action(*args, **kw)
    return str(caught.value)


def take(state: Path, **kw):
    return lock.Locks(state, host="host-a", **kw).take("vlq")


def unlock(state: Path, name: str, write_line=None, **kw) -> str:
    return lock.Locks(state, host="host-a", **kw).unlock("vlq", name, write_line=write_line)


def test_every_text_of_take_and_unlock(tmp_path, golden):
    at = tmp_path.joinpath
    at("t1").write_text("")                                     # a file where the lock folder goes
    (at("t5") / "vlq.holder").mkdir(parents=True)              # a folder where the holder file goes
    for name, value in (("t4", "not json"), ("t6", [1, 2]), ("t7", {"host": "host-b", "pid": 1}), ("t8", LIVE),
                        ("u5", "not json"), ("u6", [1, 2]), ("u7", {"host": "host-b", "pid": 1}), ("u8", LIVE),
                        ("u9", {"host": "host-b", "pid": 99}), ("u10", {"host": "host-a", "pid": DEAD})):
        holder(at(name), value)
    at("u3").mkdir()
    at("u4").mkdir()
    release = take(at("t2"))
    rows = [("take, a lock folder that cannot be made", refused(take, at("t1"))),
            ("take, a lock held by another call", refused(take, at("t2"))),
            ("unlock, a lock held by a live call", refused(unlock, at("t2"), "host-b"))]
    release()
    rows += [("take, a file system with no flock", refused(take, at("t3"), flock=no_flock)),
             ("take, a holder file that is not JSON", refused(take, at("t4"))),
             ("take, a holder file that is a folder", refused(take, at("t5"))),
             ("take, a holder file that is not an object", refused(take, at("t6"))),
             ("take, a holder of another host", refused(take, at("t7"))),
             ("take, a holder of a live process of this host", refused(take, at("t8")))]
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(lock.os, "open", denied)
        rows.append(("take, a holder file that cannot be made", refused(take, at("t9"))))
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(lock.os, "open", racing)
        rows.append(("take, a holder file made again by another call each time", refused(take, at("t10"))))
    lines = []
    rows += [("unlock, no lock folder", refused(unlock, at("absent"), "host-b")),
             ("unlock, a file system with no flock", refused(unlock, at("u3"), "host-b", flock=no_flock)),
             ("unlock, no holder file", refused(unlock, at("u4"), "host-b")),
             ("unlock, a holder file that is not JSON", refused(unlock, at("u5"), "host-b")),
             ("unlock, a holder file that is not an object", refused(unlock, at("u6"), "host-b")),
             ("unlock, a holder of another host than the one named", refused(unlock, at("u7"), "host-c")),
             ("unlock, a holder of a live process of this host", refused(unlock, at("u8"), "host-a")),
             ("unlock, a holder of another host", unlock(at("u9"), "host-b", write_line=lines.append)),
             ("the line of that unlock", json.dumps(lines)),
             ("unlock, a holder of this host whose process has ended", unlock(at("u10"), "host-a"))]
    golden("units_lock_messages", "".join(f"{case}:\n  {text}\n" for case, text in rows),
           masks={f"live process {os.getpid()} on": "live process <PID> on"})


def test_the_holder_file_a_take_makes(tmp_path, clock, golden):
    release = take(tmp_path, pid=4321, started=clock.utc().isoformat())
    text = (tmp_path / "vlq.holder").read_text(encoding="utf-8")
    release()
    assert not (tmp_path / "vlq.holder").exists()
    golden("units_lock_holder", text)


@pytest.mark.parametrize("other", [{"host": "host-b", "pid": 4321, "started": ""},
                                   {"host": "host-a", "pid": 4321, "started": "", "note": "x"}])
def test_release_keeps_a_holder_file_that_another_process_rewrote(tmp_path, other):
    release = take(tmp_path, pid=4321)
    path = tmp_path / "vlq.holder"
    path.write_text(json.dumps(other) + "\n")
    before = path.read_bytes()
    release()
    assert path.read_bytes() == before


def test_unlock_from_the_command_line(places, clock, capsys, golden):
    log, path = places.state / "unlock.jsonl", places.state / "vlq.holder"
    rows = []

    def unlocked(name: str) -> int:
        capsys.readouterr()
        code = main(places, clock, "unlock", "vlq", "--host", name)
        rows.append(f"$ qdevices unlock vlq --host {name}\n{capsys.readouterr().out}exit {code}\n")
        return code

    assert unlocked("host-b") == 1 and log.read_bytes() == b""       # no holder file; the log is opened first
    path.write_text(json.dumps({"host": "host-b", "pid": 99, "started": ""}))
    assert unlocked("host-c") == 1 and path.exists() and log.read_bytes() == b""
    assert unlocked("host-b") == 0 and not path.exists() and len(lines_of(log)) == 1
    assert unlocked("host-b") == 1 and len(lines_of(log)) == 1
    golden("units_lock_cli_unlock", "".join(rows) + "unlock.jsonl:\n" + log.read_text(encoding="utf-8"))
