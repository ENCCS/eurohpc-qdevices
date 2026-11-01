"""The record files at a place: the records of this app below a folder, and the records of older runners."""

import fnmatch
import json
import os
import stat
from abc import ABC, abstractmethod
from collections.abc import Callable, Hashable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple, NoReturn, Self, TypeVar

from .record import NAME, RecordError

FIRST_LINE: Final = 1 << 20          # the longest first line read to find a start line; a longer one raises
_T = TypeVar("_T")


class Unread(NamedTuple):
    """An older record folder, a PATH or a decisions file that cannot be read: an error line in place of it."""

    path: str
    error: str


@dataclass(frozen=True, slots=True)
class _Finder(ABC):
    """The record files at one place; a folder or file of it that cannot be read is a RecordError with its path."""

    place: Path

    @abstractmethod
    def files(self) -> list[Path]:
        """The record files at the place, in order; RecordError when a part of it cannot be read."""

    def listed(self) -> list[Path | Unread]:
        """The record files at the place, or one Unread with the place and what failed."""
        try:
            return self.files()
        except RecordError as exc:
            return [Unread(str(self.place.absolute()), str(exc))]

    def _walk(self, keep: Callable[[str], object]) -> list[Path]:
        return [Path(root) / name for root, _, names in os.walk(self.place, onerror=self._raise)
                for name in names if keep(name)]

    def _raise(self, exc: OSError) -> NoReturn:
        raise RecordError.unreadable(exc.filename or self.place, exc) from None


@dataclass(frozen=True, slots=True)
class AppRecords(_Finder):
    """The records of this app below a folder, told by their names."""

    def files(self) -> list[Path]:
        """The records below the folder, sorted by folder and name; none when the folder does not exist."""
        try:
            self.place.stat()
        except FileNotFoundError:
            return []
        except OSError as exc:
            self._raise(exc)
        return sorted(self._walk(NAME.fullmatch), key=lambda p: (p.parent, p.name))

    def newest(self) -> Path | None:
        """The newest record in the folder itself, by its name; None when it holds none."""
        found = sorted(p for p in self.place.glob("run_*.jsonl") if NAME.fullmatch(p.name))
        return found[-1] if found else None


@dataclass(frozen=True, slots=True)
class OlderRecords(_Finder):
    """The records at a place of older_records or a PATH: the file itself, or the records below the folder."""

    @classmethod
    def at(cls, place: str | Path) -> Self:
        """The records at a place of older_records, with ~ expanded."""
        return cls(Path(place).expanduser())

    @classmethod
    def listed_in(cls, site_config: dict) -> Iterator[Self]:
        """The records at each place of older_records of a site, in order, each made just before it is given."""
        for place in site_config["older_records"]:
            try:
                found = cls.at(place)
            except RuntimeError:          # a ~ that names no home folder here: a place that cannot be read
                found = _NoHome(Path(place))
            yield found

    def files(self) -> list[Path]:
        """The place when it is a file; else the .jsonl files below it named run* or with a start line, by path."""
        try:
            if self.place.is_file():
                return [self.place]
        except OSError as exc:
            self._raise(exc)
        found = self._walk(lambda name: fnmatch.fnmatchcase(name, "*.jsonl"))
        return sorted(p for p in found if fnmatch.fnmatchcase(p.name, "run*.jsonl") or self._starts(p))

    @staticmethod
    def _starts(path: Path) -> bool:
        try:
            if not stat.S_ISREG(path.stat().st_mode):
                return False
            with path.open("rb") as fh:
                first = fh.readline(FIRST_LINE + 1)
        except OSError as exc:
            raise RecordError.unreadable(path, exc) from None
        if len(first) > FIRST_LINE and not first.endswith(b"\n"):
            raise RecordError(f"{path} cannot be read: its first line is longer than {FIRST_LINE >> 20} MiB, so it "
                              "cannot be told whether it is a record; list each record of its folder by its own path",
                              path)
        try:
            line = json.loads(first.decode("utf-8"))
        except (ValueError, RecursionError):
            return False
        return isinstance(line, dict) and line.get("event") == "start"


@dataclass(frozen=True, slots=True)
class _NoHome(OlderRecords):
    """A place of older_records whose ~ names no home folder here; shown as given."""

    def files(self) -> list[Path]:
        raise RecordError(self._error(), self.place)

    def listed(self) -> list[Path | Unread]:
        return [Unread(str(self.place), self._error())]

    def _error(self) -> str:
        return f"{self.place} cannot be read: its ~ names no home folder here"


def real(path: Path) -> Path:
    """The path with its links followed, a key of `unique`; a link loop keeps its absolute path, and its read fails."""
    try:
        return path.resolve()
    except RuntimeError:                  # a symlink loop
        return path.absolute()


def unique(items: Iterable[_T], key: Callable[[_T], Hashable]) -> Iterator[_T]:
    """Each item whose key was not seen before, in order; each key is made just before its item is given."""
    seen: set[Hashable] = set()
    for item in items:
        mark = key(item)
        if mark not in seen:
            seen.add(mark)
            yield item
