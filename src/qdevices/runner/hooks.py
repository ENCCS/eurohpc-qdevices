"""The rules at their four points, and what a verdict does: a "rule" line, then a stop or a skip."""

import json
from typing import Any, Final

from ..config import Windows
from ..errors import described
from ..ledger import job_id, seconds_of
from ..qasm import Qasm
from ..rules import GENERIC, Point, checked, shot_state, verdict
from .call import Call
from .stop import StopKind

_WITH_STATE: Final = frozenset({Point.BEFORE_JOB, Point.AFTER_RESULT})     # the state reads the token and can raise


def _plain(value: object) -> Any:
    """A copy made of dicts, lists, texts and numbers only: what a rule gets."""
    return json.loads(json.dumps(value, default=str))


def _plain_job(job: dict) -> dict:
    """A job as a rule sees it: no file text."""
    return _plain({k: v for k, v in job.items() if k != "text"})


def _in_state(line: dict) -> dict:
    """A result line as a rule sees it in `state["results"]`: id, counts, seconds and any calibration set."""
    out = {"id": line.get("id", job_id(line)), "counts": line.get("counts"), "seconds": seconds_of(line)}
    if "calibration_set" in line:
        out["calibration_set"] = line["calibration_set"]
    return out


def _verdicts_of(point: str, user: dict, *args) -> list[dict]:
    """The verdicts of one point: the generic rules, then the user's rule (which replaces it at on_refusal)."""
    out = []
    if not (point == Point.ON_REFUSAL and point in user):
        out += [checked(rule(*args), rule.__name__) for rule in GENERIC[point]]
    if point in user:
        try:
            out.append(_plain(checked(user[point](*args), point)))       # plain here: str() of a value can raise
        except (Exception, SystemExit, GeneratorExit) as exc:      # an interrupt stays an interrupt
            out.append(verdict(point, False, f"the hook {point} raised {described(exc)}"))
    return out


def at(call: Call, point: Point, *values: object, job: dict | None = None) -> None:
    """The rules of a call at a point, and what their verdicts write; a failed one stops the call."""
    args = [] if job is None else [_plain_job(job)]
    args += [_plain(value) for value in values]
    if point in _WITH_STATE:
        args.append(_state(call, job))
    verdicts = _verdicts_of(point.value, call.user, *args)
    _apply(call, point.value, verdicts, None if job is None else job["order"])


def _state(call: Call, job: dict) -> dict:
    """The state a rule gets at a job, with the gate count of its text: plain values, no site object, no token."""
    text = job.get("text")
    return _plain({"site": call.site.name, "machine": call.man["machine"], "project": call.man["project"],
                   "used_seconds": call.used(), "budget_seconds": call.site_config["budget_seconds"],
                   "job_seconds_limit": call.job_limit, "wait_seconds": float(call.site_config["wait_seconds"]),
                   **shot_state(call.site_config, call.site.max_shots),
                   "max_shots_times_gates": call.site.max_shots_times_gates,
                   "gate_count": None if text is None else Qasm.parse(text.decode("utf-8", "replace")).gate_count,
                   "token_seconds_left": call.site.token_seconds_left(),
                   "in_window": Windows.of(call.site_config).now(call.clock.utc()),
                   "now_utc": call.clock.utc().isoformat(),
                   "results": {o: _in_state(r) for o, r in call.results.items()},
                   "sent": sorted(call.sent), "skipped": sorted(call.skipped), "record": str(call.rec.path)})


def _apply(call: Call, point: str, verdicts: list[dict], order: int | None) -> None:
    for v in verdicts:
        fields = {k: x for k, x in v.items() if k not in ("event", "utc", "point", "order", *call.rec.base)}
        call.rec.write("rule", point=point, order=order, **fields)
        call.say(f"  rule {v['rule']}: " + ("pass" if v["passed"] else f"NOT MET: {v['reason']}"))
        if v.get("note"):
            call.say(f"  NOTE: {v['note']}")
    failed = [v for v in verdicts if not v["passed"]]
    if failed:
        call.stop(StopKind.RULE, f"rule {failed[0]['rule']}: {failed[0]['reason']}", rule=failed[0]["rule"],
                  order=order)
    _skip(call, verdicts, order)


def _skip(call: Call, verdicts: list[dict], order: int | None) -> None:
    skips = sorted({o for v in verdicts for o in v["skip"]})
    if not skips:
        return
    bad = [o for o in skips if not 1 <= o <= len(call.man["jobs"]) or o in call.touched()]
    if bad:
        call.stop(StopKind.RULE, f"a rule names orders to skip that were sent or do not exist: {bad}", order=order)
    call.rec.write("skip", orders=skips, after_order=order, rules=[v["rule"] for v in verdicts if v["skip"]])
    call.skipped |= set(skips)
    call.say(f"  SKIP: the orders {skips} are not sent")
