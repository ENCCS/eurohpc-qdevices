"""The rules of a run: the points they run at, the form of a verdict, and the generic rules (content/rules.md)."""

import math
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from .screen import quoted
from .sites import SITES
from .sites.facts import Profile
from .values import is_int


class Point(StrEnum):
    """The four points a rule runs at."""

    BEFORE_CALL = "before_call"
    BEFORE_JOB = "before_job"
    AFTER_RESULT = "after_result"
    ON_REFUSAL = "on_refusal"


def verdict(rule: str, passed: bool, reason: str | None = None, skip=(), **values) -> dict:
    """A verdict in the fixed form: the rule, whether it passed, why not, the orders to skip, and its values."""
    return {"rule": rule, "passed": bool(passed), "reason": None if passed else reason, "skip": list(skip), **values}


def checked(raw: object, where: str) -> dict:
    """A verdict in the fixed form, or a failed verdict that says why it is not one."""
    if not isinstance(raw, dict) or not isinstance(raw.get("passed"), bool):
        return verdict(where, False, f"the hook {where} did not answer with a verdict")
    skip, rule = raw.get("skip") or [], str(raw.get("rule") or where)
    if not isinstance(skip, list) or not all(is_int(o) for o in skip):
        return verdict(rule, False, f"the hook {where} gave a skip that is not a list of orders")
    bad = [key for key in raw if not isinstance(key, str) or key == "self"]        # not a keyword of the write
    if bad:
        return verdict(rule, False, f"the hook {where} gave a key that a record line cannot hold: {bad[0]!r}")
    return {**raw, "rule": rule, "skip": skip,
            "reason": None if raw["passed"] else str(raw.get("reason") or "no reason given")}


# --------------------------------------------------------------------- the generic rules

def _profile(site: object) -> Profile | None:
    return SITES[site].profile if site in tuple(SITES) else None      # a tuple: an unhashable value is no site


def _one(fact: str) -> Profile:
    found = [cls.profile for cls in SITES.values() if getattr(cls.profile, fact)]
    if len(found) != 1:           # a read holds no site name, so the fact must be of one site only
        raise LookupError(f"the read rules take {fact} from the one site that sets it, and {len(found)} sites do")
    return found[0]


def machine_ready(read: dict) -> dict:
    """The rule "machine": where the read says, the token is a member of its project and the machine is online."""
    if "member" in read and read["member"] is not True:
        profile = _one("member_key")
        label = dict(profile.route_keys)[profile.member_key]
        return verdict("machine", False, f"the token is not a member of the {label} {read.get(profile.member_key)}")
    if "online" in read and read["online"] is not True:
        return verdict("machine", False, f"the machine {read.get('machine')} is not online")
    return verdict("machine", True)


def _listed(names: list[str]) -> str:
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def site_status(read: dict) -> dict:
    """The flags of the public status file in the read. A flag that is false stops the call; all else passes."""
    if "status" not in read:
        return verdict("site_status", True)
    profile = _one("status_rows")
    status = read["status"] if isinstance(read["status"], dict) else {}
    flags = status.get("flags")
    if not isinstance(flags, dict):
        why = status.get("error") or "the read holds no flags"
        return verdict("site_status", True, note=f"the {profile.title} status file could not be read: {why}")
    down = [row for flag, row in profile.status_rows if flags.get(flag) is False]
    if down:
        return verdict("site_status", False, f"the {profile.title} status file shows {_listed(down)} down", down=down)
    unclear = [row for flag, row in profile.status_rows if not isinstance(flags.get(flag), bool)]
    if unclear:
        return verdict("site_status", True,
                       note=f"the {profile.title} status file does not show {_listed(unclear)} as up or down")
    return verdict("site_status", True)


def shot_limit(job: dict, state: dict) -> dict:
    """The rule "shots": the shots of a job are within the lower of the limits of the site and of qdevices.toml."""
    limits = [n for n in (state.get("site_max_shots"), state.get("max_shots")) if n is not None]
    most = min(limits) if limits else None
    return verdict("shots", most is None or job["shots"] <= most,
                   f"{job['shots']} shots, the limit is {most}", shots=job["shots"], limit=most)


def gate_limit(job: dict, state: dict) -> dict:
    """Where the site has a limit of shots times gates a job: the job is within it."""
    most, gates = state.get("max_shots_times_gates"), state.get("gate_count")
    if most is None:
        return verdict("shots_times_gates", True)
    holder = _profile(state.get("site")) or next(        # no site named: the first site that holds such a limit
        (cls.profile for cls in SITES.values() if cls.max_shots_times_gates is not None), None)
    by = "" if holder is None else f" ({holder.operator})"
    if gates is None:
        return verdict("shots_times_gates", True, limit=most, note="the gate operations of the text cannot be "
                       f"counted, so its shots times gates is not checked against the {most:,} a job may hold{by}")
    product = job["shots"] * gates
    return verdict("shots_times_gates", product <= most, f"{job['shots']:,} shots times {gates:,} gates is "
                   f"{product:,}, above the {most:,} shots times gates a job may hold{by}", gate_count=gates,
                   shots_times_gates=product, limit=most)


def budget(job: dict, state: dict) -> dict:
    """The rule "budget": the seconds used and the job time limit of this job fit in budget_seconds."""
    used, limit, most = state["used_seconds"], state["job_seconds_limit"], state["budget_seconds"]
    passed = most is not None and used + limit <= most
    reason = "no budget_seconds in qdevices.toml for this site" if most is None else (
        f"{used:.1f} s used and {limit:.0f} s for this job (the job time limit) exceed the budget of {most:.0f} s")
    return verdict("budget", passed, reason, used_seconds=used, job_seconds_limit=limit, budget_seconds=most)


def token_time(job: dict, state: dict) -> dict:
    """Where the site has a token rule: the token has its least time left, or its waits of wait_seconds if longer."""
    left, wait = state.get("token_seconds_left"), state.get("wait_seconds")
    profile = _profile(state.get("site"))
    if profile is None or profile.token_min_seconds is None:
        return verdict("token", True)
    needed = max(profile.token_min_seconds, profile.token_waits * wait if isinstance(wait, (int, float)) else 0)
    passed = left is not None and left >= needed
    return verdict("token", passed, "the time left on the token cannot be read" if left is None else
                   f"the token has {int(left // 60)} minutes left, fewer than {math.ceil(needed / 60)}",
                   minutes_left=None if left is None else int(left // 60), minutes_needed=math.ceil(needed / 60))


def window(job: dict, state: dict) -> dict:
    """The rule "window": the time is not outside the window of qdevices.toml."""
    inside = state.get("in_window")
    return verdict("window", inside is not False, "the time is outside the window of qdevices.toml",
                   in_window=inside)


def all_shots(job: dict, result: dict, state: dict) -> dict:
    """The rule "all_shots": the result has counts by bit string, and they add up to the shots of the job."""
    counts = result.get("counts")
    good = isinstance(counts, dict) and counts and all(
        isinstance(k, str) and k and not set(k) - {"0", "1"} for k in counts) and all(
        is_int(n) and n >= 0 for n in counts.values())
    returned = sum(counts.values()) if good else None
    return verdict("all_shots", good and returned == job["shots"],
                   "the result has no counts by bit string" if not good else
                   f"{returned} shots returned, {job['shots']} asked", returned=returned)


def job_time(job: dict, result: dict, state: dict) -> dict:
    """The rule "job_time": the result has measured seconds, from zero to the job time limit."""
    seconds, limit = result.get("seconds"), state["job_seconds_limit"]
    passed = isinstance(seconds, (int, float)) and 0 <= seconds <= limit
    reason = ("the job has no measured time" if seconds is None else
              f"{seconds:.1f} s, the job time limit is {limit:.0f} s")
    if isinstance(seconds, (int, float)) and seconds > limit:
        record = quoted(state["record"]) if state.get("record") else "RECORD"
        reason += (". If that time is a wait at the site, not the run of the job, record your decision with: "
                   f"qdevices resolve {record} {job['order']} --over-limit")
    return verdict("job_time", passed, reason, seconds=seconds)


def stop_on_refusal(job: dict, info: dict) -> dict:
    """The rule "refusal": a refusal, a failed job or a job never submitted stops the call."""
    return verdict("refusal", False, f"order {job['order']} ({job['name']}): {info.get('kind')}: "
                   f"{info.get('reason') or 'no reason given'}")


# Read by a Point or by its text, as a member hashes as its text.
GENERIC: Final = MappingProxyType({
    Point.BEFORE_CALL: (machine_ready, site_status),
    Point.BEFORE_JOB: (shot_limit, gate_limit, budget, token_time, window),
    Point.AFTER_RESULT: (all_shots, job_time),
    Point.ON_REFUSAL: (stop_on_refusal,),
})
