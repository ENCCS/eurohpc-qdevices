"""`send`: one live call. The checks of the arguments, the lock, the signals, the record, then the loop."""

from contextlib import ExitStack, suppress
from pathlib import Path

from .. import manifest as manifests
from ..clock import Clock, Sleep
from ..lock import Locks
from ..screen import say as default_say
from ..sites import SITES
from .call import Call
from .loop import Loop
from .opening import NewRecord
from .preflight import check_arguments, check_stage
from .resume import Resume
from .rulesfile import RulesFile
from .signals import KillsAsInterrupt


def send(manifest_path, site, *, cfg: dict, places, clock: Clock, sleep: Sleep, host: str, max_order: int | None = None,
         resume: Path | None = None, new_run: bool = False, user_rules: dict | None = None, take_lock=None,
         say=default_say, rules_file: dict | None = None, new_rules: bool = False) -> int:
    """One live call. The site, clock, sleep and lock are passed in; `rules_file` names the file of `user_rules`."""
    check_stage(max_order=max_order, resume=resume, new_run=new_run, new_rules=new_rules)
    man = manifests.load(manifest_path, SITES)
    site_config = check_arguments(man, site, cfg, max_order=max_order)
    locks = Locks(places.state, host=host, started=clock.utc().isoformat())
    kind, own = (Resume, {"path": resume}) if resume is not None else (NewRecord, {"new_run": new_run})
    with ExitStack() as held:
        held.enter_context(locks.held(site.name, take=take_lock))      # before any record is read
        held.enter_context(KillsAsInterrupt())                          # restored before the lock is released
        opening = kind(man=man, site=site, site_config=site_config, places=places, clock=clock, host=host,
                       max_order=max_order, say=say, rules_file=RulesFile(rules_file), new_rules=new_rules, **own)
        opened = opening.open()
        held.callback(_close, opened.rec)                               # closed before the signals are restored
        call = Call.from_opening(man, site, site_config, opened, clock=clock, sleep=sleep, say=say,
                                 user=user_rules or {})
        return Loop(call, max_order, opened.tell).run()


def _close(rec) -> None:
    with suppress(OSError):           # each line is synced: a failed close leaves the exit code of the loop
        rec.close()
