"""One live call per site at a time: a `flock` on <site>.lock and an O_EXCL holder file <site>.holder.

The holder file is there because a cluster file system can grant a `flock` per node with no error.
"""

import fcntl
import json
import os
import socket
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Final, TextIO, TypeAlias

from .errors import Refused

_Release: TypeAlias = Callable[[], None]          # what a take returns: the release of the lock
TakeLock: TypeAlias = Callable[[str], _Release]   # Locks.take, or a test's own
this_host: Final = socket.gethostname


class LockRefused(Refused):
    """The site lock cannot be taken. Nothing is sent."""


def _alive(pid: object) -> bool:
    """True when `pid` is a live process of this host; False for a value that is not an int above 0."""
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, OverflowError):      # OverflowError: above any pid
        return False
    except PermissionError:
        return True
    return True


def _read_holder(path: Path) -> dict:
    """The holder file, as the dict that was read; LockRefused when it cannot be read or is not an object."""
    try:
        holder = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise LockRefused(f"the holder file {path} cannot be read ({type(exc).__name__}); "
                          "check it and remove it by hand") from None
    if not isinstance(holder, dict):
        raise LockRefused(f"the holder file {path} is not in the form of this app")
    return holder


def _make_holder(path: Path, holder: dict) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, (json.dumps(holder) + "\n").encode())
        os.fsync(fd)
    finally:
        os.close(fd)


def _release(fh: TextIO, path: Path, mine: dict) -> None:
    try:
        if _read_holder(path) == mine:
            path.unlink()
    except (LockRefused, OSError):
        pass
    fh.close()


class Locks:
    """The lock of each site in the lock folder `state`, as this host and this process take it."""

    def __init__(self, state: Path, *, host: str | None = None, pid: int | None = None, started: str = "",
                 flock: Callable[[int, int], None] = fcntl.flock) -> None:
        self.state = Path(state)
        self.host = host or this_host()
        self.pid = os.getpid() if pid is None else pid
        self.started = started              # the start time in the holder file
        self.flock = flock

    def take(self, site: str) -> _Release:
        """Take the lock of a site. The answer is a function that releases it."""
        try:
            self.state.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise LockRefused(f"the lock folder {self.state} cannot be made: {exc}") from None
        fh = self._flocked(site)
        path = self.state / f"{site}.holder"
        mine = {"host": self.host, "pid": self.pid, "started": self.started}
        try:
            self._claim(site, path, mine)
        except LockRefused:
            fh.close()
            raise
        return lambda: _release(fh, path, mine)

    @contextmanager
    def held(self, site: str, take: TakeLock | None = None) -> Iterator[None]:
        """The lock of a site for the body of a `with`, released at its end however it ends."""
        release = (take or self.take)(site)
        try:
            yield
        finally:
            release()

    def unlock(self, site: str, host_name: str, *, write_line: Callable[[dict], object] | None = None) -> str:
        """Remove a holder file left by `host_name`. The answer says what was done; LockRefused if refused."""
        if not self.state.is_dir():
            raise LockRefused(f"there is no lock folder {self.state}")
        path = self.state / f"{site}.holder"
        fh = self._flocked(site)
        try:
            if not path.exists():
                raise LockRefused(f"there is no holder file {path}")
            holder = _read_holder(path)
            if holder.get("host") != host_name:
                raise LockRefused(f"{path} names the host {holder.get('host')!r}, not {host_name!r}")
            if holder.get("host") == self.host and _alive(holder.get("pid")):
                raise LockRefused(f"{path} names the live process {holder.get('pid')} on this host")
            path.unlink()
            if write_line is not None:
                write_line({"event": "unlock", "site": site, "holder": holder, "by_host": self.host})
            return f"removed {path}, left by {host_name} (pid {holder.get('pid')})"
        finally:
            fh.close()

    def _flocked(self, site: str) -> TextIO:
        path = self.state / f"{site}.lock"
        with ExitStack() as stack:
            try:
                fh = stack.enter_context(open(path, "a", encoding="utf-8"))     # closed at a refusal
            except OSError as exc:
                raise LockRefused(f"the lock file {path} cannot be opened ({exc.strerror or exc})") from None
            try:
                self.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise LockRefused(f"another live call holds the lock {path}") from None
            except OSError as exc:
                raise LockRefused(f"the file system gives no lock at {path} ({exc.strerror or exc}); "
                                  "a live call is refused") from None
            stack.pop_all()                 # flocked: open until the release
        return fh

    def _claim(self, site: str, path: Path, mine: dict) -> None:
        for _ in range(2):
            try:
                _make_holder(path, mine)
                return
            except FileExistsError:
                self._clear(site, path)     # in the handler, so an unlink error escapes as it is
            except OSError as exc:
                raise LockRefused(f"the holder file {path} cannot be made ({exc.strerror or exc}); "
                                  "a live call is refused") from None
        raise LockRefused(f"the holder file {path} cannot be made")

    def _clear(self, site: str, path: Path) -> None:
        holder = _read_holder(path)
        if holder.get("host") != self.host:
            raise LockRefused(f"{path} names the host {holder.get('host')!r}: a live call may run "
                              f"there. Check that host, then `qdevices unlock {site} --host "
                              f"{holder.get('host')}`") from None
        if _alive(holder.get("pid")):
            raise LockRefused(f"{path} names the live process {holder.get('pid')} on this host") from None
        path.unlink()                       # a holder of this host whose process has ended
