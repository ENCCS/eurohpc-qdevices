"""The config file qdevices.toml (content/configuration.md): an unknown key is refused, so no secret goes in."""

import re
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import Refused
from .sites import SITES
from .sites.facts import SHARED_KEYS, Key

_DAYS: Final = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_WINDOW: Final = re.compile(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun)(?:-(Mon|Tue|Wed|Thu|Fri|Sat|Sun))? "
                            r"([01][0-9]|2[0-3]):([0-5][0-9])-([01][0-9]|2[0-4]):([0-5][0-9])")


class ConfigError(Refused):
    """The config file is not in the fixed schema."""


COMMON: Final = (                     # the keys that every site takes, first in a parsed table
    Key(name="projects", kind=list, default=()),
    Key(name="award_hours", kind=(int, float)),
    Key(name="budget_seconds", kind=(int, float), least=0),
    Key(name="job_seconds_limit", kind=(int, float), default=300.0, above=0),
    Key(name="wait_seconds", kind=(int, float), default=900.0),
    Key(name="max_shots", kind=int, least=1),
    Key(name="older_records", kind=list, default=()),
)


@dataclass(frozen=True, slots=True)
class Windows:
    """The windows of a site, each in the form 'Wed-Thu 14:00-18:00', and the time zone they are given in."""

    texts: Sequence[str]
    zone: str

    @classmethod
    def of(cls, site_config: dict) -> Self:
        """The windows of the config of one site."""
        return cls(site_config["window"], site_config["window_zone"])

    @staticmethod
    def _span(found: re.Match[str]) -> tuple[int, int, int, int]:
        """The first and the last day (0 is Monday), and the start and the end minute, of a window in the form."""
        first = _DAYS.index(found.group(1))
        last = _DAYS.index(found.group(2)) if found.group(2) else first
        start, end = int(found.group(3)) * 60 + int(found.group(4)), int(found.group(5)) * 60 + int(found.group(6))
        return first, last, start, end

    def check(self, site: str) -> None:
        """Refuse a window not in the form, a window that wraps or is empty, and a zone that is not known."""
        for text in self.texts:
            found = _WINDOW.fullmatch(text)
            if not found:
                raise ConfigError(f"[{site}] window {text!r} is not in the form 'Wed-Thu 14:00-18:00'")
            first, last, start, end = self._span(found)
            if last < first or end <= start:
                raise ConfigError(f"[{site}] window {text!r} wraps or is empty: a window does not wrap, so give "
                                  "Fri-Sun and Mon as two windows, and an end after the start within one day, in the "
                                  "form 'Wed-Thu 14:00-18:00'")
        if self.texts:
            try:
                ZoneInfo(self.zone)
            except (ZoneInfoNotFoundError, ValueError, OSError):
                raise ConfigError(f"[{site}] window_zone {self.zone!r} is not a known time zone, such as "
                                  "'Europe/Warsaw'") from None

    def holds(self, now: datetime) -> bool:
        """True if `now`, already in the zone of the windows, is inside one of them."""
        day, minute = now.weekday(), now.hour * 60 + now.minute
        for text in self.texts:
            first, last, start, end = self._span(_WINDOW.fullmatch(text))
            if first <= day <= last and start <= minute < end:
                return True
        return False

    def now(self, utc: datetime) -> bool | None:
        """Whether a time in UTC is inside a window; None for a site with no window."""
        if not self.texts:
            return None
        return self.holds(utc.astimezone(ZoneInfo(self.zone)))


def _keys() -> dict[str, Key]:
    keys: dict[str, Key] = {}
    for key in (*COMMON, *(row for name in SITES for row in SITES[name].profile.config_keys), *SHARED_KEYS):
        keys.setdefault(key.name, key)            # each name once, in its first place
    return keys


def _site(site: str, table: object) -> dict:
    if not isinstance(table, dict):
        raise ConfigError(f"[{site}] is not a table")
    keys = _keys()
    allowed = sorted({key.name for key in (*COMMON, *SITES[site].profile.config_keys)})
    # every key, each site with its own lists
    out = {name: list(key.default) if key.kind is list else key.default for name, key in keys.items()}
    for name, value in table.items():
        if name not in allowed:
            raise ConfigError(f"[{site}] has the unknown key {name!r}; the keys are {', '.join(allowed)}")
        problem = keys[name].problem(value)
        if problem is not None:
            raise ConfigError(f"[{site}] {name} {problem}")
        out[name] = value
    Windows.of(out).check(site)
    return out


def parse(text: str) -> dict:
    """The config of every site in a text of qdevices.toml, each with all the keys and the defaults filled in."""
    try:
        raw = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"the config is not TOML: {exc}") from None
    except RecursionError:
        raise ConfigError("the config is not TOML: it is nested too deep") from None
    sites = tuple(SITES)
    unknown = sorted(set(raw) - set(sites))
    if unknown:
        raise ConfigError(f"the config has the unknown table {unknown[0]!r}; the tables are {', '.join(sites)}")
    return {site: _site(site, raw.get(site, {})) for site in sites}


def load(path: Path) -> dict:
    """The config of every site. A file that does not exist gives the defaults (no project allowed)."""
    path = Path(path)
    if not path.exists():
        return parse("")
    try:
        return parse(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"{path} cannot be read: {exc}") from None
    except UnicodeDecodeError:
        raise ConfigError(f"{path} cannot be read: it is not UTF-8 text") from None


def project_problems(man: dict, site_config: dict) -> list[str]:
    """The project of a manifest against the list of its site in config, then the checks of the site's own keys."""
    problems = []
    if man["project"] not in site_config["projects"]:
        problems.append(f"the project {man['project']!r} is not listed for {man['site']} in qdevices.toml")
    return problems + SITES[man["site"]].config_problems(man, site_config)
