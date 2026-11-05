"""The command line: qdevices check, dry-run, send, resolve, unlock, runs, jobs, usage, login.

Only `send --live --max-order N` sends. No flag or environment variable moves a site address or a folder of the app.
"""

import argparse
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Final, TypeAlias

from .. import __version__, resolve
from .. import config as configs
from ..clock import CLOCK, SLEEP
from ..errors import Refused
from ..lock import this_host
from ..paths import Places
from ..screen import finish, say
from ..sites import SITES
from ..sites import make_site as default_make_site
from .commands import NO_DECISIONS, Commands

__all__ = ["NO_DECISIONS", "Commands", "main", "parser"]

_Row: TypeAlias = tuple[tuple[str, ...], dict[str, Any]]    # the flags and keywords of one add_argument
_Help: TypeAlias = str | Callable[[dict[str, object]], str]  # a text, or the text made of what the sites give
_ONE_OF: Final = ()                # the flags of a row that opens a required group: one of the rows after it
_SITE: Final = ("site",)           # a site of the registry, whose names are the choices
_PATHS: Final[_Row] = (("paths",), {"nargs": "*", "type": Path,
                                    "help": "more records or folders, of this app or older runners"})
# Each command: its name, its help and its rows, in the order of the help. Five helps are made from _texts().
_SPECS: Final[tuple[tuple[str, _Help, tuple[_Row, ...]], ...]] = (
    ("check", "the token and, with --live, one read of the machine (no job)", (
        (_SITE, {}),
        (("--live",), {"action": "store_true", "help": "one read of the machine, stored as a file"}),
        (("--manifest",), {"type": Path, "help": lambda t: f"read the machine of this manifest{t['routed']}"}))),
    ("dry-run", "check a manifest offline: no network, no token", (
        (("manifest",), {"type": Path}),
        (("--read",), {"type": Path, "help": "a saved read (default: the newest of `check --live`)"}))),
    ("send", "send the jobs of a manifest, one at a time (needs --live)", (
        (("manifest",), {"type": Path}),
        (("--live",), {"action": "store_true", "help": "a live call; without it nothing is sent"}),
        (("--max-order",), {"type": int, "metavar": "N", "help": "send the orders up to N"}),
        (("--resume",), {"type": Path, "metavar": "FILE",
                         "help": "go on with a record; without --max-order: collect only"}),
        (("--new-run",), {"action": "store_true", "help": "a new record that sends the first orders again"}),
        (("--new-rules",), {"action": "store_true",
                            "help": "with --resume: send with a rules file other than the one the record is held to"}),
        (("--rules",), {"type": Path, "metavar": "FILE", "help": "a Python file with the rules of an experiment"}))),
    ("resolve", lambda t: f"record what became of a lost order, of a {t['two_step']}job whose submit request may "
                          "have reached the site, of a job the site showed only as New for days, of a result above "
                          "job_seconds_limit, of a result that cannot be read, or of a result or a job the site no "
                          "longer gives (offline)", (
        (("record",), {"type": Path}),
        (("order",), {"type": int}),
        (_ONE_OF, {"required": True}),
        (("--job",), {"metavar": "ID",
                      "help": lambda t: f"the job id found in the job list of the site{t['unlisted']}"}),
        (("--none",), {"action": "store_true", "help": "the site shows no job, shows that the job never ran, or "
                                                       "showed it only as New for days (not cancelled)"}),
        (("--over-limit",), {"action": "store_true", "help": "the seconds of the result are a wait at the site: it "
                                                             "counts at job_seconds_limit"}),
        (("--expired",), {"action": "store_true", "help": lambda t: f"two calls, {t['expired_minutes']} minutes or "
                                                                    "more apart, stopped at result_expired: final, "
                                                                    "it counts at job_seconds_limit"}),
        (("--unreadable",), {"action": "store_true",
                             "help": lambda t: f"two calls stopped at result_error, {t['expired_minutes']} minutes or "
                                               "more apart on an answer that could not be used, else "
                                               f"{t['unanswered_hours']} hours or more apart: the job finished, its "
                                               "result cannot be read; final, it counts at job_seconds_limit"}),
        (("--gone",), {"action": "store_true", "help": "a record of another runner: the site no longer gives the "
                                                       "job of an open order; final, it counts at "
                                                       "job_seconds_limit"}))),
    ("unlock", "remove a holder file left by another host (offline)", (
        (_SITE, {}),
        (("--host",), {"required": True, "metavar": "NAME"}))),
    ("runs", "one line for each record", (_PATHS,)),
    ("usage", "totals by site and project", (_PATHS,)),
    ("jobs", "one line for each order of a record", ((("record",), {"type": Path}),)),
    ("login", "how to get the token of a site", ((_SITE, {}),)),
)


def _texts() -> dict[str, object]:
    """The parts of the help that the sites and resolve give, by the names that the helps of _SPECS read."""
    classes = tuple(SITES.values())
    routed = ", ".join(cls.name for cls in classes if cls.profile.route_keys)
    unlisted = ", ".join(f"{cls.profile.title} has none: ask {cls.profile.operator}" for cls in classes
                         if not cls.profile.job_list)
    return {"routed": f" (needed for {routed})" if routed else "", "two_step": resolve.two_step_titles(),
            "unlisted": f" ({unlisted})" if unlisted else "", "expired_minutes": resolve.EXPIRED_MINUTES,
            "unanswered_hours": resolve.UNANSWERED_HOURS}


def _text(text: _Help, filled: dict[str, object]) -> str:
    return text(filled) if callable(text) else text


def parser() -> argparse.ArgumentParser:
    """The parser of the command line: the rows of _SPECS, the site names as choices of a site."""
    filled = _texts()
    ap = argparse.ArgumentParser(prog="qdevices", description=(__doc__ or "").split("\n")[0])     # none under -OO
    ap.add_argument("--version", action="version", version=f"qdevices {__version__}")
    sub = ap.add_subparsers(dest="command")
    for name, text, rows in _SPECS:
        into = command = sub.add_parser(name, help=_text(text, filled))
        for flags, given in rows:
            if flags == _ONE_OF:
                into = command.add_mutually_exclusive_group(**given)
                continue
            found = {**given, "help": _text(given["help"], filled)} if "help" in given else given
            into.add_argument(*flags, **({"choices": sorted(SITES), **found} if flags == _SITE else found))
    return ap


def main(argv=None, *, places=None, environ=None, make_site=None, clock=None, sleep=None, host=None) -> int:
    """`qdevices ARGS`: one command, and its exit code; a refusal prints REFUSED and gives 1."""
    try:
        return _command(argv, places=places, environ=environ, make_site=make_site, clock=clock, sleep=sleep,
                        host=host)
    finally:
        finish()          # the exit code stays; stderr tells of a screen that cannot be written, not of a closed pipe


def _command(argv, *, places, environ, make_site, clock, sleep, host) -> int:
    ap = parser()
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:         # argparse exits 2 on a wrong argument; here 2 is a stop by a rule
        return 0 if exc.code in (0, None) else 1
    if args.command is None:
        ap.print_help()
        say("\nThe bare command sends nothing.")
        return 1
    places = places or Places.default()
    environ = os.environ if environ is None else environ
    make_site = make_site or default_make_site
    clock, sleep, host = clock or CLOCK, sleep or SLEEP, host or this_host()
    try:
        return Commands(places=places, cfg=configs.load(places.config), environ=environ, make_site=make_site,
                        clock=clock, sleep=sleep, host=host).run(args)
    except Refused as exc:        # also those of the lock, manifest, config and rules file
        say(f"REFUSED: {exc}")
        return 1
