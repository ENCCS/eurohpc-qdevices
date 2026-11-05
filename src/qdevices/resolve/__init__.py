"""`qdevices resolve`: record what became of an order. Offline, under the site lock, one synced line.

A lost order is never sent again, no job is cancelled, and a record of another runner is never written.
"""

from pathlib import Path

from ..clock import Clock
from ..lock import TakeLock
from ..paths import Places
from .app import AppResolution, two_step_titles
from .names import DECISIONS, flag, joined
from .other import OtherResolution
from .resolution import Resolution
from .stops import EXPIRED_MINUTES, UNANSWERED_HOURS, answered

__all__ = ["DECISIONS", "EXPIRED_MINUTES", "UNANSWERED_HOURS", "answered", "flag", "joined", "resolve",
           "two_step_titles"]


def resolve(record_path, order: int, job_id: str | None, *, places: Places, clock: Clock, host: str,
            take_lock: TakeLock | None = None, decision: str | None = None, cfg: dict | None = None) -> str:
    """One synced "resolved" line: of the decision, else of `job_id`, an id or None (--none).

    `decision` is a name of DECISIONS: "over_limit", "expired", "unreadable" or "gone".
    """
    path = Path(record_path)
    events = Resolution.read(path)
    kind = AppResolution if AppResolution.owns(path, events, places.records) else OtherResolution
    return kind(path=path, order=order, job_id=job_id, decision=decision, places=places, clock=clock, host=host,
                take_lock=take_lock, cfg=cfg, events=events).run()
