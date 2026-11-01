"""`qdevices dry-run`: the checks of a manifest against a saved read and the limits. It makes no network call."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from . import billing, layout, rules
from . import manifest as manifests
from .clock import CLOCK, Clock
from .config import project_problems
from .qasm import Qasm
from .saved_reads import SavedReads
from .screen import quoted
from .screen import say as default_say
from .sites import SITES


def _failed(say: Callable[[str], None], problems: list[str]) -> int:
    for p in problems:
        say(f"  FAILED: {p}")
    return 1


@dataclass(slots=True, kw_only=True)
class _DryRun:
    """The dry run of a manifest that could be read: its head, its checks and its plan, judged as a send judges them."""

    man: dict
    cls: type
    site_config: dict
    read_file: Path | None
    read: dict | None
    problems: list[str]
    clock: Clock
    say: Callable[[str], None]

    def report(self) -> int:
        """Print the head, the notes and the plan, then each problem: 0 when there is none, else 1."""
        self._head()
        self._plan(self._checks())
        _failed(self.say, self.problems)
        self.say("Dry run FAILED. Nothing was sent." if self.problems else "Dry run passed. Nothing was sent.")
        return 1 if self.problems else 0

    def _head(self) -> None:
        man, cls = self.man, self.cls
        self.say(f"  manifest  {man['path']}  SHA-256 {man['sha256']}")
        self.say(f"  site      {man['site']}, machine {man['machine']}, project {man['project']}"
                 + "".join(f", {what} {man[key]}" for key, what in cls.profile.route_keys))
        self.say(f"  run       {man['run']}")
        now = self.clock.utc()                 # read even when no read is saved
        if self.read_file is None:
            self.say(f"  read      no read of {man['machine']} is saved: qubits and gates are checked only where the "
                     "text alone allows")
            return
        hours = SavedReads.hours_old(self.read, now)
        self.say(f"  read      {self.read_file}, " + ("age not known" if hours is None else f"{hours:.1f} hours old"))
        if hours is not None and hours > 24:
            self.say(f"  note      the read is older than 24 hours and the machine may have changed since: read it "
                     f"again with qdevices check {man['site']} --live --manifest {quoted(man['path'])}")
        if isinstance(self.read, dict) and self.read.get("layout_sha256"):
            self.say(f"  layout    {self.read.get('qubits')} qubits, {self.read.get('pairs')} pairs, layout_sha256 "
                     f"{self.read['layout_sha256']}")

    def _checks(self) -> int | None:
        man, cls, site_config = self.man, self.cls, self.site_config
        self.problems += project_problems(man, site_config)
        pin = layout.Pin.of(man, cls)
        self.problems += pin.form_problems if self.read_file is None else pin.problems(self.read)
        if pin.given is not None and self.read_file is None:
            self.say("  note      the layout pin of the manifest is compared with a read only, and none is saved")
        if site_config["budget_seconds"] is None:
            self.problems.append(f"no budget_seconds for {man['site']} in qdevices.toml: a send is refused without it")
        site_most = site_config.get("site_max_shots") or cls.max_shots
        if cls.max_shots and site_most > cls.max_shots:
            self.say(f"  note      site_max_shots {site_most} is above the limit of {cls.max_shots} the app holds for "
                     f"{man['site']}: the site may accept such a job and not run it")
        limits = [n for n in (site_most, site_config["max_shots"]) if n is not None]
        return min(limits) if limits else None

    def _plan(self, most: int | None) -> None:
        total_shots, total_cost = 0, 0.0
        self.say("  plan")
        for job in self.man["jobs"]:
            shots, cost = self._job(job, most)
            total_shots += shots
            total_cost += cost or 0.0
        count, site = len(self.man["jobs"]), self.man["site"]
        self.say(f"  totals    {count} job{'' if count == 1 else 's'}, {total_shots} shots"
                 + (f", {total_cost:.3f} s by the published rule" if billing.publishes(site) else ""))
        self.say(f"  billing   {self.cls.profile.billing.text}")

    def _job(self, job: dict, most: int | None) -> tuple[int, float | None]:
        cls, where, shots = self.cls, f"order {job.get('order')} ({job.get('name')})", job.get("shots")
        mine = list(cls.validate(job, self.read)) if "text" in job else []
        if most is not None and isinstance(shots, int) and shots > most:
            mine.append(f"{shots} shots, the limit is {most}")
        shown, gate_problems, gate_notes = self._gates(job)
        mine += gate_problems
        counted = isinstance(shots, int) and shots <= manifests.MOST_SHOTS        # above it, refused by the manifest
        cost = billing.published_seconds(self.man["site"], shots) if counted else None
        self.say(f"    [{job.get('order')}/{len(self.man['jobs'])}] {job.get('name')!s:<12} {shots!s:>6} shots  "
                 f"{job.get('file')}  options {job.get('options') or {}}{shown}"
                 + (f"  {cost:.3f} s by the published rule" if cost is not None else "")
                 + ("  ok" if not mine else ""))
        self.problems += [f"{where}: {p}" for p in mine]
        for note in (cls.notes(job, self.read) if "text" in job else []) + gate_notes:
            self.say(f"  note      {where}: {note}")
        return (shots if isinstance(shots, int) else 0), cost

    def _gates(self, job: dict) -> tuple[str, list[str], list[str]]:
        cls = self.cls
        if cls.max_shots_times_gates is None or "text" not in job:
            return "", [], []
        gates = Qasm.parse(cls.text_of(job)).gate_count
        v = rules.gate_limit(job, {"site": cls.name, "max_shots_times_gates": cls.max_shots_times_gates,
                                   "gate_count": gates})
        notes = ([v["note"]] if v.get("note") else []) + cls.count_notes(job)
        shown = ("  gates not counted" if gates is None else
                 f"  {gates:,} gates, {v['shots_times_gates']:,} shots times gates")
        return shown, [] if v["passed"] else [v["reason"]], notes


def dry_run(manifest_path, *, cfg: dict, places, read_file=None, clock: Clock | None = None,
            say=default_say) -> int:
    """`qdevices dry-run`: the checks of a manifest against a saved read and the limits, with no network call."""
    man, problems = manifests.read(manifest_path, SITES)
    say("Dry run: no network call, no token.")
    if man is None:
        return _failed(say, problems)
    cls, site_config = SITES[man["site"]], cfg[man["site"]]
    if read_file is not None:
        read, wrong = SavedReads.load(read_file, man["machine"])
        if wrong:
            return _failed(say, [f"{read_file} {wrong}"])
    else:
        read_file, read = SavedReads.of(places, man["site"]).newest(man["machine"])
    return _DryRun(man=man, cls=cls, site_config=site_config, read_file=read_file, read=read, problems=problems,
                   clock=clock or CLOCK, say=say).report()
