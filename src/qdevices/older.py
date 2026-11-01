"""Decisions on the orders of older records, kept in a file of the app, as a record of another runner is frozen."""

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Self

from . import record as records
from .ledger import Ledger
from .sites import SITES
from .values import is_int, sha256_hex

DECISIONS: Final = "older_decisions.jsonl"   # not run*.jsonl: a scan of a folder never takes it for a record


def binding(events: list[dict]) -> dict:
    """What ties a decision to the lines of a record of another runner: the keys of the decision line, in order."""
    return {"start_sha256": start_digest(events), "lines": len(events), "lines_sha256": _lines_digest(events)}


def start_digest(events: list[dict]) -> str | None:
    """The SHA-256 (hex) of the first event of a record, as canonical JSON, when it is a start line; else None."""
    if not events or events[0].get("event") != "start":
        return None
    return sha256_hex(_canonical(events[0]))


def _made_on(events: list[dict], decision: dict) -> bool:
    """True when a record starts with the lines a decision was made on: their number and their SHA-256."""
    n = decision.get("lines")
    return is_int(n) and 0 < n <= len(events) and _lines_digest(events[:n]) == decision.get("lines_sha256")


def _lines_digest(events: list[dict]) -> str:
    return sha256_hex(b"".join(_canonical(e) + b"\n" for e in events))


def _canonical(event: dict) -> bytes:
    text = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return text.encode("utf-8", "surrogatepass")


@dataclass(frozen=True, slots=True)
class Decisions:
    """The "resolved" lines of the decisions files, by the start digest of the record each was made on."""

    by_start: dict[str, list[dict]] = field(default_factory=dict)

    @staticmethod
    def file(records_root: Path, site: str) -> Path:
        """The decisions file of a site, in its folder of the records."""
        return Path(records_root) / site / DECISIONS

    @classmethod
    def load(cls, records_root: Path, sites: Iterable[str] | None = None) -> Self:
        """The "resolved" lines of the decisions file of each site, or of those named, in file order."""
        by_start: dict[str, list[dict]] = {}
        for site in SITES if sites is None else sites:
            path = cls.file(records_root, site)
            try:
                path.stat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise records.RecordError.unreadable(path, exc) from None
            for e in records.RecordLines.read(path).events:     # its RecordError carries the path
                if e.get("event") == "resolved" and isinstance(e.get("start_sha256"), str):
                    by_start.setdefault(e["start_sha256"], []).append(e)
        return cls(by_start)

    def merged(self, events: list[dict]) -> list[dict]:
        """The events of a record that is not the app's, then the decisions made on its lines; else the events."""
        digest = None if Ledger(events).is_app else start_digest(events)
        found = [d for d in self.by_start.get(digest, ()) if _made_on(events, d)] if digest else []
        return events + found if found else events
