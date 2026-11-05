"""The commands of the command line, one method each, with what a command needs held once."""

import argparse
from collections.abc import Callable, MutableMapping
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .. import check as checks
from .. import manifest as manifests
from .. import monitor, older, resolve, rulebook, runner
from .. import record as records
from ..clock import Clock, Sleep
from ..dryrun import dry_run
from ..errors import Refused
from ..ledger import Ledger
from ..lock import Locks
from ..paths import Places
from ..screen import say
from ..sites import SITES

_NOTHING: Final = "Nothing is sent: `send` needs --live, and --max-order N (send) or --resume FILE (collect)."
NO_DECISIONS: Final = "the older records are in the totals below, read without the decisions of this file"
_EXPORT: Final = 'Then, in the shell of the call:   set +x; export {token_env}="$(cat FILE)"'  # the end of `login`


def _say_all(lines: list[str]) -> int:
    for line in lines:
        say(line)
    return 0


@dataclass(frozen=True, slots=True, kw_only=True)
class Commands:
    """The nine commands, each a method `do_` and its name, with - as _, which gives its exit code."""

    places: Places
    cfg: dict
    environ: MutableMapping[str, str]
    make_site: Callable
    clock: Clock
    sleep: Sleep
    host: str

    def run(self, args: argparse.Namespace) -> int:
        """The command of the arguments: its exit code."""
        command = {"login": self.do_login, "check": self.do_check, "dry-run": self.do_dry_run, "send": self.do_send,
                   "resolve": self.do_resolve, "unlock": self.do_unlock, "runs": self.do_runs, "usage": self.do_usage,
                   "jobs": self.do_jobs}[args.command]
        return command(args)

    def do_login(self, args: argparse.Namespace) -> int:
        """`qdevices login SITE`: how to get the token of a site."""
        cls = SITES[args.site]
        return _say_all([*cls.profile.login, _EXPORT.format(token_env=cls.token_env)])

    def do_check(self, args: argparse.Namespace) -> int:
        """`qdevices check SITE`: the token taken out of the environment, then the check of the site."""
        token = self.environ.pop(SITES[args.site].token_env, None)
        return checks.check(args.site, live=args.live, token=token, manifest_path=args.manifest, cfg=self.cfg,
                            places=self.places, clock=self.clock, sleep=self.sleep, host=self.host,
                            make_site=self.make_site)

    def do_dry_run(self, args: argparse.Namespace) -> int:
        """`qdevices dry-run MANIFEST`: the checks of a manifest, with no network call."""
        return dry_run(args.manifest, cfg=self.cfg, places=self.places, read_file=args.read)

    def do_send(self, args: argparse.Namespace) -> int:
        """`qdevices send MANIFEST`: nothing without --live and a stage; the token out of the environment first."""
        if not args.live or (args.max_order is None and args.resume is None):
            say(_NOTHING)
            return 1
        man = manifests.load(args.manifest, SITES)
        cls = SITES[man["site"]]
        token = self.environ.pop(cls.token_env, None)    # the one read; out of the environment before the rules file
        if not token:
            raise Refused(f"no token: set {cls.token_env} (see `qdevices login {man['site']}`)")
        user, rules_file = rulebook.load(args.rules)    # one read: hooks and SHA-256 of the same bytes
        with closing(self.make_site(man, man["site"], token, clock=self.clock, sleep=self.sleep,
                                    site_config=self.cfg[man["site"]])) as site:
            return runner.send(args.manifest, site, cfg=self.cfg, places=self.places, clock=self.clock,
                               sleep=self.sleep, host=self.host, max_order=args.max_order, resume=args.resume,
                               new_run=args.new_run, user_rules=user, rules_file=rules_file,
                               new_rules=args.new_rules)

    def do_resolve(self, args: argparse.Namespace) -> int:
        """`qdevices resolve RECORD ORDER`: what became of an order, by the one flag given."""
        decision = next((name for name in resolve.DECISIONS if getattr(args, name)), None)
        say(resolve.resolve(args.record, args.order, None if args.none else args.job, places=self.places,
                            clock=self.clock, host=self.host, decision=decision, cfg=self.cfg))
        return 0

    def do_unlock(self, args: argparse.Namespace) -> int:
        """`qdevices unlock SITE --host NAME`: the holder file of another host removed, with a line in unlock.jsonl."""
        with records.Record(Path(self.places.state) / "unlock.jsonl", self.clock, {"app": "qdevices"}) as log:
            say(Locks(self.places.state, host=self.host).unlock(
                args.site, args.host, write_line=lambda line: log.write(line.pop("event"), **line)))
        return 0

    def do_runs(self, args: argparse.Namespace) -> int:
        """`qdevices runs`: one line for each record, the unreadable places first."""
        unread, summaries = self._summaries(args.paths)
        return _say_all([monitor.run_line(s) for s in [*map(monitor.summary, unread), *summaries]]
                        or ["no records found"])

    def do_usage(self, args: argparse.Namespace) -> int:
        """`qdevices usage`: totals by site and project; an unreadable decisions file leaves no record out."""
        unread, summaries = self._summaries(args.paths)
        return _say_all([f"{u.path}: {u.error}; {NO_DECISIONS}" for u in unread] + monitor.usage(summaries, self.cfg)
                        or ["no records found"])

    def do_jobs(self, args: argparse.Namespace) -> int:
        """`qdevices jobs RECORD`: one line for each order of a record, with the decisions on an older one."""
        try:
            events, cut = records.RecordLines.read(args.record)
        except records.RecordError as exc:
            raise Refused(str(exc)) from None
        decisions, unread = (older.Decisions(), []) if Ledger(events).is_app else self._decisions()
        rows = [f"{u.path}: {u.error}" for u in unread] + monitor.job_rows(decisions.merged(events))
        return _say_all(rows + ([f"{len(cut)} cut lines passed over"] if cut else []))

    def _decisions(self) -> tuple[older.Decisions, list[monitor.Unread]]:
        try:
            return older.Decisions.load(self.places.records), []
        except records.RecordError as exc:
            return older.Decisions(), [monitor.Unread(str(exc.path), str(exc))]

    def _summaries(self, paths: list[Path]) -> tuple[list[monitor.Unread], list]:
        decisions, unread = self._decisions()
        return unread, [monitor.summary(p, decisions) for p in monitor.find(self.places, self.cfg, paths)]
