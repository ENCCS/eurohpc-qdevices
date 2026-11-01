"""The declared facts of a machine, one frozen Profile on its class, and the rows they are declared with.

A leaf: it imports the standard library only, so config, billing and redact can take their rows from it.
"""

import math
import re
from collections.abc import Callable
from dataclasses import KW_ONLY, dataclass
from types import MappingProxyType
from typing import Final

HIDDEN: Final = "[hidden]"            # what the token filter puts in place of a secret
_READ_KEYS: Final = ("machine", "online", "member", "qubits", "pairs", "layout_sha256", "pending_jobs", "machines",
                     "templates", "status")        # the keys of a read that `check --live` prints, in this order
SECONDS: Final = MappingProxyType({   # the words of each kind of seconds of a result, in the order of the usage text
    "device": "the device seconds of the job",
    "scheduled_to_completed": "the time from scheduled to completed",
    "wall": "wall seconds",
})


@dataclass(frozen=True, slots=True, kw_only=True)
class Key:
    """One key of a site table of qdevices.toml: its name, its type and its default."""

    name: str
    kind: type | tuple[type, ...]
    default: object = None
    least: int | None = None          # a limit of a safety rule: a lower value would turn it off
    above: int | None = None          # the same, for a limit that may be a fraction

    def problem(self, value: object) -> str | None:
        """What is wrong with a value for this key, in the words after its name in a refusal, or None for a good one."""
        if not isinstance(value, self.kind) or isinstance(value, bool):
            return "has the wrong type"
        if isinstance(value, float) and not math.isfinite(value):
            return "must be a finite number"
        if self.kind is list and not all(isinstance(item, str) for item in value):
            return "must be a list of texts"
        if self.above is not None and value <= self.above:
            return f"must be above {self.above}"
        return f"must be {self.least} or more" if self.least is not None and value < self.least else None


_WINDOW_KEY: Final = Key(name="window", kind=list, default=())
_WINDOW_ZONE_KEY: Final = Key(name="window_zone", kind=str, default="UTC")
_SITE_MAX_SHOTS_KEY: Final = Key(name="site_max_shots", kind=int, least=1)
SHARED_KEYS: Final = (_WINDOW_KEY, _WINDOW_ZONE_KEY, _SITE_MAX_SHOTS_KEY)    # in every table: generic code reads them


@dataclass(frozen=True, slots=True)
class Rule:
    """A billing rule: its text and, where published, the seconds of a shot and the floor of a job."""

    text: str
    _: KW_ONLY                        # keyword only, so the two figures cannot be swapped
    per_shot: float | None = None     # seconds a shot; None where no rule is published
    floor: float = 0.0                # seconds, the least a job is billed

    def seconds(self, shots: int) -> float | None:
        """The seconds of one job of this many shots by the published rule, or None where none is published."""
        return None if self.per_shot is None else max(shots * self.per_shot, self.floor)


@dataclass(frozen=True, slots=True, kw_only=True)
class Profile:
    """The declared facts of one machine, set once in the body of its class and read by its name in the registry."""

    title: str                            # as the texts and the manual name it
    operator: str                         # the centre that runs it
    login: tuple[str, ...]                # how to get the token: the lines of `qdevices login` before its export line
    billing: Rule
    config_keys: tuple[Key, ...] = ()     # the keys of its own in its table of qdevices.toml
    route_keys: tuple[tuple[str, str], ...] = ()      # (manifest key, label): texts a manifest gives, on every line
    older_machines: tuple[str, ...] = ()  # its machine names in the records of older runners
    numeric_ids: bool = False             # a job id of digits is a number (`resolve --job`)
    configuring_state: str | None = None  # the state of a job made and not yet submitted
    usage_note: str = ""                  # a sentence at the end of the usage text
    secret_patterns: tuple[tuple[re.Pattern[str], str], ...] = ()    # (pattern, replacement) of the token filter
    status_rows: tuple[tuple[str, str], ...] = ()     # (flag, row) of the status file in a read
    member_key: str | None = None         # the route key that the member flag of a read is about
    job_list: bool = True                 # the site lists its jobs, where `resolve --job` finds an id
    token_label: str = ""                 # the name of the token in `check`, with token_expiry
    token_expiry: Callable[[str], float | None] | None = None      # when a token expires, in seconds of the epoch
    token_min_seconds: int | None = None  # the least token time left before each job; None for no such rule
    token_waits: int = 1                  # the waits of wait_seconds in an order, for that rule
    read_keys: tuple[str, ...] = _READ_KEYS    # the keys of a read that `check --live` prints

    def __post_init__(self) -> None:
        wrong = [rule for holds, rule in self._rules() if not holds]
        if wrong:
            raise TypeError(f"the profile {self.title!r}: {'; '.join(wrong)}")
        for pattern, replacement in self.secret_patterns:
            pattern.sub(replacement, "")      # a bad group reference fails here, not at a line of a record

    def _rules(self) -> tuple[tuple[bool, str], ...]:
        texts = self._texts
        pairs = all(isinstance(rows, tuple) and all(texts(row, 2) for row in rows)
                    for rows in (self.route_keys, self.status_rows))
        patterns = isinstance(self.secret_patterns, tuple) and all(
            isinstance(row, tuple) and len(row) == 2 and isinstance(row[0], re.Pattern) and isinstance(row[1], str)
            for row in self.secret_patterns)
        routes = [row[0] for row in self.route_keys] if pairs else []
        expiry = self.token_expiry is None or callable(self.token_expiry)
        return ((texts((self.title, self.operator)), "title and operator must be texts"),
                (bool(self.login) and texts(self.login), "login must be one or more lines of text"),
                (texts(self.older_machines) and texts(self.read_keys), "older_machines and read_keys must be texts"),
                (isinstance(self.billing, Rule), "billing must be a Rule"),
                (isinstance(self.config_keys, tuple) and all(isinstance(key, Key) for key in self.config_keys),
                 "config_keys must be Key rows"),
                (pairs, "route_keys and status_rows must be pairs of texts"),
                (patterns, "secret_patterns must be pairs of a compiled pattern and its replacement"),
                (self.member_key is None or self.member_key in routes, "member_key must be one of the route keys"),
                (expiry and bool(self.token_label) == (self.token_expiry is not None),
                 "token_label and token_expiry, a function, come together"),
                (self.token_waits == 1 or self.token_min_seconds is not None, "token_waits needs token_min_seconds"))

    @staticmethod
    def _texts(values: object, width: int | None = None) -> bool:
        return (isinstance(values, tuple) and width in (None, len(values))
                and all(isinstance(value, str) and value for value in values))
