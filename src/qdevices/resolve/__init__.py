"""`qdevices resolve`: record what became of an order. Offline, under the site lock, one synced line.

A lost order is never sent again, no job is cancelled, and a record of another runner is never written.
"""

from pathlib import Path

from .. import record as records
from ..clock import Clock
from ..errors import Refused
from ..lock import TakeLock
from ..paths import Places
from .app import EXPIRED_MINUTES, AppResolution, two_step_titles
from .other import OtherResolution

__all__ = ["EXPIRED_MINUTES", "resolve", "two_step_titles"]


def resolve(record_path, order: int, job_id: str | None, *, places: Places, clock: Clock, host: str,
            take_lock: TakeLock | None = None, decision: str | None = None, cfg: dict | None = None) -> str:
    """One synced "resolved" line. `decision` is "over_limit", "expired" or "gone"; else `job_id` is an id or None."""
    path = Path(record_path)
    try:
        events, _ = records.RecordLines.read(path)
    except records.RecordError as exc:
        raise Refused(str(exc)) from None
    kind = AppResolution if AppResolution.owns(path, events, places.records) else OtherResolution
    return kind(path=path, order=order, job_id=job_id, decision=decision, places=places, clock=clock, host=host,
                take_lock=take_lock, cfg=cfg, events=events).run()
