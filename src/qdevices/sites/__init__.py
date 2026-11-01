"""The site classes by name: the one place where a machine is registered, each class checked at import."""

import re
from itertools import combinations
from types import MappingProxyType
from typing import TYPE_CHECKING, Final

from .euroqexa import EuroQExa
from .facts import Profile
from .piastq import PiastQ
from .vlq import VLQ

if TYPE_CHECKING:
    import httpx

    from ..clock import Clock, Sleep
    from .base import Site

__all__ = ["SITES", "make_site"]

_NAME: Final = re.compile(r"[a-z][a-z0-9]{0,8}")       # a site name; the usage table pads it to 9
_OWN: Final = ("name", "token_env")                    # set, with the profile, in each class's own body
_ONE_CLASS: Final = ("status_rows", "member_key")      # the read rules take each from the one class that sets it


def _shared(a: type["Site"], b: type["Site"]) -> list[str]:
    both, rows = f"{a.__name__} and {b.__name__}", {key.name: key for key in a.profile.config_keys}
    problems = [f"{both} share {a.token_env} with other addresses"] if (
        a.token_env == b.token_env and set(a.addresses) != set(b.addresses)) else []
    problems += [f"{both} both name the older machine {machine!r}" for machine in a.profile.older_machines
                 if machine in b.profile.older_machines]
    problems += [f"{both} declare the config key {key.name!r} with other rows" for key in b.profile.config_keys
                 if rows.get(key.name, key) != key]
    return problems + [f"{both} both set {fact}" for fact in _ONE_CLASS
                       if getattr(a.profile, fact) and getattr(b.profile, fact)]


def _registry(classes: tuple[type["Site"], ...]) -> dict[str, type["Site"]]:
    problems = [f"{cls.__name__} does not set {fact} in its own body" for cls in classes for fact in _OWN
                if fact not in vars(cls)]
    problems += [f"{cls.__name__} does not set profile = Profile(...) in its own body" for cls in classes
                 if not isinstance(vars(cls).get("profile"), Profile)]
    if not problems:                  # the checks below read the facts that those give
        names = [cls.name for cls in classes]
        problems += [f"the site name {name!r} is not of the form {_NAME.pattern}" for name in names
                     if not (isinstance(name, str) and _NAME.fullmatch(name))]
        problems += [f"the site name {name!r} is given twice" for i, name in enumerate(names) if name in names[:i]]
        problems += [problem for pair in combinations(classes, 2) for problem in _shared(*pair)]
    if problems:
        raise TypeError(f"the sites cannot be registered: {'; '.join(problems)}")
    return {cls.name: cls for cls in classes}


_REGISTRY: Final = _registry((EuroQExa, VLQ, PiastQ))     # a new machine goes at the end, so every order holds
SITES: Final = MappingProxyType(_REGISTRY)


def make_site(manifest: dict | None, name: str, token: str, *, clock: "Clock", sleep: "Sleep", site_config: dict,
              transport: "httpx.BaseTransport | None" = None) -> "Site":
    """A site object for a manifest (or for a site name alone, for `check`)."""
    site_class = SITES[name]
    float(site_config["wait_seconds"])      # for every site: a value float() refuses fails here, before any client
    return site_class.from_manifest(manifest or {}, token, clock=clock, sleep=sleep, site_config=site_config,
                                    transport=transport)
