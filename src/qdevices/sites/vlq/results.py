"""What the two result files of a VLQ job give, read through the restricted reader."""

import math
from dataclasses import dataclass, field
from typing import Final, Self

from ...values import is_int, is_number
from ..pickle_reader import Walk, items_of, loads, state_of, uuid_text

MAX_DEPTH: Final = 8              # the deepest level of a search; calibration_set_id is 4 levels down


@dataclass(slots=True, kw_only=True)
class _Search:
    """One search of a loaded results file: its walk, and what it has found so far."""

    walk: Walk = field(default_factory=Walk)
    counts: dict[str, int] | None = None
    success: bool | None = None
    shots: int | None = None
    ids: set[str | None] = field(default_factory=set)

    def visit(self, node: object, depth: int = 0) -> None:
        if depth > MAX_DEPTH or not self.walk.due(node, depth):
            return
        items = items_of(node)
        if items and self.counts is None and all(isinstance(k, str) for k in items):
            self.counts = {k: v for k, v in items.items() if is_int(v)} or None
        for key, value in self.walk.fields(node):
            if key == "success" and isinstance(value, bool) and self.success is None:
                self.success = value
            elif key == "shots" and isinstance(value, int) and self.shots is None:
                self.shots = value
            elif key == "calibration_set_id":
                self.ids.add(uuid_text(value))
            self.visit(value, depth + 1)
        for item in self.walk.entries(node):
            self.visit(item, depth + 1)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResultsFile:
    """The counts, the success flag, the shots and the calibration set of a results file; None where not found."""

    counts: dict[str, int] | None
    success: bool | None
    shots: int | None
    calibration_set: str | None       # only when the file names one calibration set

    @classmethod
    def parse(cls, data: bytes) -> Self:
        """The answer of a results file, by a bounded search. PickleRefused for a file that is not read."""
        search = _Search()
        search.visit(loads(data))
        search.ids.discard(None)
        return cls(counts=search.counts, success=search.success, shots=search.shots,
                   calibration_set=search.ids.pop() if len(search.ids) == 1 else None)

    @staticmethod
    def names_seconds(data: bytes) -> bool:
        """True when the job file holds `remote_hw_runtime` at all, of any value."""
        return "remote_hw_runtime" in state_of(loads(data))

    @staticmethod
    def device_seconds(data: bytes) -> float | None:
        """The device seconds the service measured (`remote_hw_runtime` of the job file), if finite and 0 or more."""
        value = state_of(loads(data)).get("remote_hw_runtime")
        try:
            seconds = float(value) if is_number(value) else math.nan
        except OverflowError:                 # an int beyond the floats
            seconds = math.nan
        return seconds if math.isfinite(seconds) and seconds >= 0 else None
