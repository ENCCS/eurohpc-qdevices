"""The orders of a manifest in turn, the end line, and an interrupt or an error of the program."""

import traceback
from collections.abc import Callable
from dataclasses import dataclass

from ..layout import Pin
from ..ledger import Ledger, Order, Status
from ..redact import redact
from ..rules import Point
from ..screen import warn
from ..sites.base import SiteError
from . import hooks
from .call import Call
from .collect import Collect
from .stop import StopKind, Stopped, UnderWay
from .submit import JobSend


@dataclass(slots=True)
class Loop:
    """The orders of one call in turn, up to max_order, with one read of the machine before the first job."""

    call: Call
    max_order: int | None
    first: Callable[[], None] = lambda: None          # the first texts of the opening of the record
    read_done: bool = False

    def run(self) -> int:
        """Every order in turn, to the first stop, then the end line: the exit code. No line is left unwritten."""
        call = self.call
        states = Ledger(call.prior).orders
        try:
            self.first()
            return self._orders(states)
        except KeyboardInterrupt as exc:
            return self._interrupted(exc)
        except Exception as exc:
            return self._broken(exc)
        finally:
            try:
                call.write_unwritten()
            except Exception:
                pass

    def _orders(self, states: dict[int, Order]) -> int:
        """The orders to the first stop, whose code is read inside the try of `run`, then the end line."""
        try:
            for job in self.call.man["jobs"]:
                if not self._order(job, states.get(job["order"])):
                    break
        except Stopped as stop:
            return stop.kind.code
        return self._end()

    def _order(self, job: dict, o: Order | None) -> bool:
        """One order: False ends the loop. An order that is final is passed over and never sent again."""
        call, order, name = self.call, job["order"], job["name"]
        tag = f"[{order}/{len(call.man['jobs'])}] {name}"
        call.under_way = UnderWay()
        match o.status if o else Status.UNSENT:
            case Status.FINAL:
                call.say(f"{tag}: {o.final} in the record, not sent again")
            case Status.OPEN:
                call.say(f"{tag}: job {o.id} has no result in the record; collecting it")
                # A lost order given an id by `resolve --job` has no 'submitted' line: its 'submitting' utc stands in.
                call.site.sent_at(o.id, call.submitted_utc(order) or call.submitting_utc(order))
                Collect(call, job, o.id, o.submitted, None).run()
            case Status.LOST:
                call.stop(StopKind.LOST, f"order {order} ({name}) has a 'submitting' line and no job id: the request "
                          f"may have reached the site. It is never sent again. {call.site.lost_note}, then record "
                          f"what you found: {call.resolve_command(order, '--job ID (or --none)')}",
                          order=order, name=name)
            case Status.UNSENT:
                return self._unsent(job, tag)
        return True

    def _unsent(self, job: dict, tag: str) -> bool:
        call = self.call
        if job["order"] in call.skipped:
            call.say(f"{tag}: skipped by a rule")
            return True
        if self.max_order is None or job["order"] > self.max_order:
            return False
        call.say(f"{tag}: sending")
        if not self.read_done:
            self._gate()
        JobSend(call, job).run()
        return True

    def _gate(self) -> None:
        """Before the first job of a call: one read of the machine, the rules on it, the check of every job."""
        call = self.call
        try:
            read = call.site.read()
        except SiteError as exc:
            call.stop(StopKind.READ, f"the machine cannot be read: {call.error(exc)['error']}. Nothing was sent in "
                      "this call", **call.error(exc))
        jobs = call.man["jobs"]
        notes = [f"order {j['order']} ({j['name']}): {n}" for j in jobs for n in call.site.notes(j, read)]
        call.rec.write("read", read=read, **({"notes": notes} if notes else {}))
        for n in notes:
            call.say(f"  NOTE: {n}")
        hooks.at(call, Point.BEFORE_CALL, read)
        problems = Pin.of(call.man, call.site).problems(read)
        problems += [f"order {j['order']} ({j['name']}): {p}" for j in jobs for p in call.site.validate(j, read)]
        if problems:
            for p in problems:
                call.say(f"  {p}")
            call.stop(StopKind.CHECK, "the check of the jobs against the read of this call failed. Nothing was sent "
                      "in this call", problems=problems)
        self.read_done = True

    def _end(self) -> int:
        """The "end" line: what is final and what is left to send."""
        call = self.call
        now = Ledger(call.lines())
        left = [j["order"] for j in call.man["jobs"] if now.status(j["order"]) == Status.UNSENT
                and j["order"] not in call.skipped]
        reason = "every order is final" if not left else f"the orders {left} are not sent"
        call.rec.write("end", reason=reason, results=len(call.results), left=left, used_seconds=call.used())
        call.say(f"End: {reason}. {len(call.results)} results in the record. Record: {call.rec.path}")
        if left:
            call.say(f"Go on with: {call.resume_command(' --max-order N')}")
        return 0

    def _interrupted(self, exc: KeyboardInterrupt) -> int:
        call = self.call
        who = exc.args[0] if exc.args else "Ctrl-C"
        reason = f"interrupted by {who}; nothing was cancelled"
        for write in _writes(call, lambda: call.rec.write("stop", kind=StopKind.INTERRUPT.value, reason=reason,
                                                          **call.under_way.fields())):
            try:
                write()
            except OSError as error:      # the text and the job under way are still shown
                warn(redact(f"RECORD WRITE FAILED ({type(error).__name__}): a line of the interrupt may not be in "
                            "the record", call.secrets()))
        call.say(f"\nInterrupted by {who}. Nothing was cancelled. Collect with: {call.resume_command()}")
        if call.under_way.text:
            call.say(call.under_way.text)
        if call.under_way.held.get("id") is not None and call.site.collect_note:
            call.say(call.site.collect_note)        # an open order: when to collect it
        return StopKind.INTERRUPT.code

    def _broken(self, exc: Exception) -> int:
        call = self.call
        reason = f"an error of the program: {type(exc).__name__}: {exc}"[:500]
        for write in _writes(call, lambda: call.rec.write("stop", kind=StopKind.ERROR.value, reason=reason,
                                                          **call.under_way.fields())):
            try:
                write()
            except Exception:
                pass
        warn(redact(traceback.format_exc(), call.secrets()) + "FAILED: an error of the program in a live call. A job "
             f"may be at the site: read the record {call.rec.path} before the next step.")
        if call.under_way.text:
            warn(redact(call.under_way.text, call.secrets()))
        return StopKind.ERROR.code


def _writes(call: Call, stop: Callable[[], object]) -> tuple[Callable[[], object], ...]:
    """The "submitted" line not yet on disk, then the stop line: each tried, so a failed one does not skip the other."""
    return call.write_unwritten, stop
