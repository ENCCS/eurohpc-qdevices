"""What the app asks of a site: its profile, facts and steps, the words of its notes, a job's state and a refusal.

A site calls `note` after each request that can make a job exist, before the next, and never cancels or retries.
"""

from abc import abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Final, NotRequired, Protocol, TypeAlias, TypedDict

from .facts import Profile

if TYPE_CHECKING:
    from .base import SiteError

Note: TypeAlias = Callable[..., None]      # the synced line of one step, with the ids it names

# The words of a note that the app reads by name.
INIT: Final = "init"                      # the start of the step of each note in prepare, whose line is an "init" line
INIT_JOB: Final = "init_job"              # the key of the id that a note in prepare names
INIT_CREATED: Final = "init_created"      # the step once the work before the job is made: usage counts its id
INIT_STATUS: Final = "init_status"        # the step of its end, with its NODE_SECONDS
NODE_SECONDS: Final = "node_seconds"      # the node seconds that the work before the job booked
TABLE_NOTE: Final = "table_note"          # a text of a note in prepare, which the call prints
JOB: Final = "job"                        # the key of the job id in a note in submit
MADE_STATE: Final = "Configuring"         # the state of a job made, not yet submitted, at a site that names none


class JobState(TypedDict):
    """The answer of `status`: the name of the state, whether it ends the wait, and whether it is a success."""

    state: str
    final: bool
    ok: bool
    configuring: bool                     # made and not yet submitted (VLQ)
    code: NotRequired[int]                # the HEAppE number of the state (VLQ)


@dataclass(frozen=True, slots=True)
class Refusal:
    """The answers to the job request of a site that are refusals: no job ran, so the order is final."""

    step: str                                             # the request that the site can refuse
    codes: frozenset[int]                                 # the HTTP statuses of a refusal
    body: Callable[[str | None], object] | None = None    # true for a refusal; read only at one of the codes

    def classify(self, error: "SiteError") -> str:
        """Either "refused" (no job ran, the order is final) or "unknown" (a job may exist)."""
        refused = error.status_at(self.step) in self.codes and (self.body is None or self.body(error.body))
        return "refused" if refused else "unknown"


class SiteProtocol(Protocol):
    """What the app asks of a site class: its profile, its facts with their defaults, and its steps."""

    profile: Profile                      # set in each registered class; read as SITES[name].profile, never on a site
    name: str = ""
    token_env: str = ""
    addresses: tuple[str, ...] = ()                       # fixed: no flag and no environment variable moves them
    options: Mapping[str, type] = MappingProxyType({})    # option name -> type, checked in the manifest
    max_shots: int | None = None                          # one job's limit; config site_max_shots replaces it
    max_shots_times_gates: int | None = None              # per job (rules.gate_limit); None for no limit
    seconds_kind: str = "device"                          # what the seconds of a result are: "device", "wall", ...
    poll_seconds: float = 5.0
    # Step lines once a job is made and just before its submit request (VLQ); None where one request does both.
    made_step: str | None = None
    submit_step: str | None = None
    collect_note: str = ""                # in a stop that leaves an order open: when to collect it ("" for none)
    lost_note: str = "Look for it in the job list of the site"    # in the stop at a lost order
    layout_pin: bool = False              # the read gives a layout, so "layout" in a manifest pins it (layout.py)

    @abstractmethod
    def read(self) -> dict:
        """One read of the machine, which makes no job. The read rules judge its keys online, member and status."""

    @classmethod
    @abstractmethod
    def validate(cls, job: dict, read: dict | None) -> list[str]:
        """Offline: the problems of one job against a saved read."""

    @staticmethod
    def notes(job: dict, read: dict | None) -> list[str]:
        """Offline: what the check of one job against a read notes without failing it."""
        return []

    @staticmethod
    def count_notes(job: dict) -> list[str]:
        """Offline: what the dry run notes on the gate count of one job, where max_shots_times_gates is set."""
        return []

    @staticmethod
    def config_problems(man: dict, site_config: dict) -> list[str]:
        """Offline: the problems of a manifest against the site's own keys in its table of qdevices.toml."""
        return []

    def sent_at(self, job_id: object, submitted_utc: str | None) -> None:
        """The app's submitted_utc of a job before its wait, or its 'submitting' utc for an id from `resolve --job`."""

    def prepare(self, job: dict, note: Note) -> object:
        """Work before the job (an init job), given to `submit`; a note comes before each job request it makes."""
        return None

    @abstractmethod
    def submit(self, job: dict, note: Note, prepared: object) -> object:
        """Make the job and send it; the answer is its id. Job requests go only here and in `prepare`."""

    @abstractmethod
    def status(self, job_id: object) -> JobState:
        """{"state", "final", "ok", "configuring"}. It raises `base.Expired` when the site no longer knows the job."""

    @abstractmethod
    def result(self, job_id: object) -> dict:
        """{"counts", "seconds", ...}. It raises `base.Expired` when the site no longer knows the job."""

    @abstractmethod
    def classify(self, error: Exception) -> str:
        """Either "refused" (no job ran, the order is final) or "unknown" (a job may exist)."""

    def logs(self, job_id: object) -> dict:
        """What the site keeps of a job that failed, for its "failed" line; empty where it keeps nothing."""
        return {}

    @abstractmethod
    def secrets(self) -> list[str]:
        """What the token filter takes out of each line: the token, and each password made, before the next request."""

    def token_seconds_left(self) -> float | None:
        """The seconds before the token expires, or None where they cannot be read."""
        return None

    @abstractmethod
    def close(self) -> None:
        """Close each client of the site, with no request, as its constructor makes none."""
