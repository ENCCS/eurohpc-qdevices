"""The record of a run: one JSON line for each event, appended and synced to disk as it happens.

A line is on disk before its write returns: fsync, and F_FULLFSYNC as a macOS fsync stops at the drive cache.

Event names written by this app: start, resume, read, rule, skip, init, submitting, step, submitted,
status, result, refused, failed, not_submitted, resolved, stop, end, unlock.
"""

import contextlib
import fcntl
import json
import os
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Final, NamedTuple, Self

from .clock import Clock
from .redact import redact_all

NAME: Final = re.compile(r"run_[0-9]{8}T[0-9]{6}Z\.jsonl")


class RecordError(Exception):
    """A record, or a place of records, that cannot be read; `path` is the file or folder that failed."""

    def __init__(self, text: str, path: Path | str | None = None) -> None:
        super().__init__(text)
        self.path = path

    @classmethod
    def unreadable(cls, path: Path | str, exc: OSError) -> Self:
        """The error of a place whose read failed: its path as given, and the kind of the error."""
        return cls(f"{path} cannot be read: {type(exc).__name__}", path)


def _utf8(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _sync(fd: int) -> None:
    os.fsync(fd)
    full = getattr(fcntl, "F_FULLFSYNC", None)
    if full is not None:
        with contextlib.suppress(OSError):      # not on this file system; the fsync is done
            fcntl.fcntl(fd, full)


def _sync_folder(folder: Path) -> None:
    """The sync of a folder, so a new name in it is on disk; a folder that cannot be synced is passed over."""
    try:
        fd = os.open(folder, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


class Record:
    """One record, open to append. Every text of a line goes through the token filter first."""

    def __init__(self, path: Path, clock: Clock, base: dict,
                 secrets: Callable[[], Iterable[str]] = lambda: ()) -> None:
        self.path = Path(path)
        self.clock = clock
        self.base = dict(base)
        self.secrets = secrets
        self.lines: list[dict] = []   # this process's lines, unfiltered, for the rules of this call
        new = not self.path.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ragged = not new and self.path.stat().st_size > 0 and not self.path.read_bytes().endswith(b"\n")
        self._fh = open(self.path, "a", encoding="utf-8")
        if ragged:
            self._fh.write("\n")      # ends a cut last line, so the next line starts clean
            self._fh.flush()
            _sync(self._fh.fileno())
        if new:
            _sync_folder(self.path.parent)
            _sync_folder(self.path.parent.parent)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, kind: object, *exc: object) -> None:
        if kind is None:
            self.close()
        else:
            with contextlib.suppress(OSError):        # the error on its way out stays the one shown
                self.close()

    def write(self, event: str, **fields: object) -> dict:
        """The line of an event as this process made it, once its filtered text is on disk."""
        line = {"event": event, "utc": self.clock.utc().isoformat(), **self.base, **fields}
        filtered = redact_all(line, list(self.secrets()))
        text = json.dumps(filtered, default=str, ensure_ascii=False)
        if not text.isascii() and not _utf8(text):
            text = json.dumps(filtered, default=str)              # a lone surrogate kept as its escape
        self._fh.write(text + "\n")
        self._fh.flush()
        _sync(self._fh.fileno())
        self.lines.append(line)
        return line

    def close(self) -> None:
        """The close of the file of the record."""
        self._fh.close()


class RecordLines(NamedTuple):
    """The events of a record, and its cut lines (number, text). A cut line is never an error."""

    events: list[dict]
    cut: list[tuple[int, str]]

    @classmethod
    def read(cls, path: Path) -> Self:
        """The lines of the record at a path; RecordError when no file is there or it cannot be read."""
        path = Path(path)
        try:
            if not path.is_file():
                raise RecordError(f"no record at {path}", path)
            data = path.read_bytes()
        except OSError as exc:
            raise RecordError.unreadable(path, exc) from None
        return cls.parse(data)

    @classmethod
    def parse(cls, data: bytes) -> Self:
        """The lines of the bytes of a record, each line read as UTF-8 on its own."""
        events, cut = [], []
        for number, raw in enumerate(data.split(b"\n"), 1):
            try:
                row = raw.decode("utf-8")
            except UnicodeDecodeError:
                cut.append((number, raw.decode("utf-8", "replace")))
                continue
            if not row.strip():
                continue
            try:
                event = json.loads(row)
            except (ValueError, RecursionError):
                event = None
            if isinstance(event, dict):
                events.append(event)
            else:
                cut.append((number, row))
        return cls(events, cut)
