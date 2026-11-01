"""The billing rule of each site and the award totals; the app never claims what a site bills."""

from .sites import SITES
from .sites.facts import SECONDS


def published_seconds(site: str, shots: int) -> float | None:
    """The seconds of one job by the published rule, or None where no rule is published."""
    cls = SITES.get(site)
    return None if cls is None else cls.profile.billing.seconds(shots)


def publishes(site: str) -> bool:
    """Whether the site publishes seconds by the shot: the dry run totals them, and `runs` and `usage` show them."""
    cls = SITES.get(site)
    return cls is not None and cls.profile.billing.per_shot is not None


def usage_words() -> tuple[str, str]:
    """The words of what each site measures, kind by kind in the order of SECONDS, and each usage note after a space."""
    classes = tuple(SITES.values())
    measured = ", ".join(f"{cls.profile.title} {words}" for kind, words in SECONDS.items() for cls in classes
                         if cls.seconds_kind == kind)
    return measured, "".join(f" {cls.profile.usage_note}" for cls in classes if cls.profile.usage_note)


def award_seconds(site_config: dict) -> float | None:
    """The seconds of the award of a site, from award_hours in its config, or None where it gives none."""
    hours = site_config.get("award_hours")
    return None if hours is None else float(hours) * 3600.0
