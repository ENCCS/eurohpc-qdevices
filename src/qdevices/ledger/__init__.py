"""The state of each order of a record, read from its lines: final, open, lost or unsent. Reads only.

A lost order ("submitting", no job id) may have reached the site: it is never sent again, and blocks a new run.
"""

from functools import cached_property
from typing import Any

from ..sites import SITES
from ..values import is_int
from .kinds import ID_KEYS, Outcome, Status, job_id, seconds_of
from .order import Order

__all__ = ["ID_KEYS", "Ledger", "Order", "Outcome", "Status", "job_id", "seconds_of"]


class Ledger:
    """What the lines of one record say; make a new one after a write, as nothing here follows the record."""

    def __init__(self, events: list[dict]) -> None:
        self.events = events

    @cached_property
    def orders(self) -> dict[int, Order]:
        """Order -> what the record says of it, in the order of the first line of each."""
        out: dict[int, Order] = {}
        for e in self.events:
            order = e.get("order")
            if is_int(order) and e.get("event") is not None:
                out.setdefault(order, Order(order=order)).apply(e)
        for o in out.values():
            o.settle()
        return out

    @property
    def site(self) -> str | None:
        """The site of a record: its "site" field, or the machine of an older record."""
        names = tuple(SITES)              # a tuple: a value that cannot be hashed is no site
        for e in self.events:
            if e.get("site") in names:
                return e["site"]
        machines = {machine: name for name in names for machine in SITES[name].profile.older_machines}
        for e in self.events:
            if isinstance(e.get("machine"), str) and e["machine"] in machines:      # a list cannot be a key
                return machines[e["machine"]]
        return None

    @property
    def skipped(self) -> set[int]:
        """The orders that a skip line names; orders that are not a list of whole numbers name none."""
        return {o for e in self.events if e.get("event") == "skip" and isinstance(e.get("orders"), list)
                for o in e["orders"] if is_int(o)}

    def first(self, key: str) -> Any:
        """The first truthy value of a key in the lines; None when no line has one."""
        return next((e[key] for e in self.events if e.get(key)), None)

    @property
    def project(self) -> Any:
        """The first truthy "project" of the lines, else their first truthy "proposal", else None."""
        return self.first("project") or self.first("proposal")

    @property
    def start(self) -> dict | None:
        """The first line whose event is "start", or None."""
        return next((e for e in self.events if e.get("event") == "start"), None)

    @property
    def is_app(self) -> bool:
        """True when the first start line is one of this app: it holds "app": "qdevices"."""
        start = self.start
        return start is not None and start.get("app") == "qdevices"

    def status(self, order: int) -> Status:
        """The status of an order; unsent when no line names it."""
        o = self.orders.get(order)
        return o.status if o else Status.UNSENT

    def lines_of(self, order: int, kind: str) -> list[dict]:
        """The lines of a kind for an order, by ==: an order of 1.0 or true is 1, though the fold passes it over."""
        return [e for e in self.events if e.get("event") == kind and e.get("order") == order]

    @property
    def open_or_lost(self) -> list[tuple[int, Status]]:
        """(order, status) for each order that is open or lost."""
        return [(n, o.status) for n, o in sorted(self.orders.items()) if o.status in (Status.OPEN, Status.LOST)]

    @property
    def any_sent(self) -> bool:
        """True when an order was asked for or has a job id."""
        return any(o.asked or o.id is not None for o in self.orders.values())

    def used_seconds(self, job_limit: float) -> float:
        """The seconds of a record for the budget: those of its orders, rounded to 6 places."""
        total = 0.0
        for o in self.orders.values():      # a loop: sum() compensates floats, and gives another total
            total += o.budget(job_limit)
        return round(total, 6)
