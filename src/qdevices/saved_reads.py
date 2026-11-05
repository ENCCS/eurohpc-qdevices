"""The saved reads of a site: stored by `check --live`, read by the dry run. A list of the machines names none."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Self

from .clock import Clock, stamp
from .redact import redact
from .values import standard_json


@dataclass(frozen=True, slots=True)
class SavedReads:
    """The folder of the saved reads of one site: a read of a machine, or a list of the machines of the site."""

    folder: Path

    @classmethod
    def of(cls, places, site: str) -> Self:
        """The saved reads of a site, in the reads folder of the app."""
        return cls(Path(places.reads) / site)

    @staticmethod
    def kind(read: dict) -> str:
        """`read` for a read of a machine; `list` for a list of the machines of a site, which names none."""
        return "read" if read.get("machine") else "list"

    def save(self, read: dict, clock: Clock, secrets: Callable[[], list[str]]) -> Path:
        """Store a read under the time of the call, with the secrets of the site, read last, hidden: the file."""
        self.folder.mkdir(parents=True, exist_ok=True)
        file = self.folder / f"{self.kind(read)}_{stamp(clock.utc())}.json"
        held = standard_json({"read_at": clock.utc().isoformat(), **read})
        text = redact(json.dumps(held, indent=1, default=str), secrets())
        file.write_text(text + "\n", encoding="utf-8")
        return file

    def newest(self, machine: str | None) -> tuple[Path | None, dict | None]:
        """The newest saved read of a machine and its file; a list of the machines is passed over."""
        for file in sorted(self.folder.glob("read_*.json"), reverse=True):
            read, wrong = self.load(file, machine)
            if not wrong:
                return file, read
        return None, None

    @classmethod
    def load(cls, file, machine) -> tuple[dict | None, str | None]:
        """The read in a file, or why it is not a read of the machine: not JSON, no machine named, or another."""
        try:
            read = json.loads(Path(file).read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            return None, "cannot be read as JSON"
        if not isinstance(read, dict) or cls.kind(read) == "list":
            return None, (f"names no machine, so it is not a read of {machine} (a list of the machines of a site "
                          "names none)")
        named = read["machine"]
        return (read, None) if named == machine else (None, f"is a read of {named}, not of {machine}")

    @staticmethod
    def hours_old(read: dict, now: datetime) -> float | None:
        """The age of a read in hours, by the time it was stored; None when that time cannot be read."""
        try:
            return (now - datetime.fromisoformat(str(read.get("read_at")))).total_seconds() / 3600
        except (AttributeError, TypeError, ValueError):
            return None
