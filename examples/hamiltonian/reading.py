"""The counts of a job as shares, raw and with the conservation check, and a whole run. Standard library only."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.request import urlopen

from chain import T

HEAD: Final = (f"{'job':<11} {'t':>4} {'N':>2} {'2q':>3} {'key':>4} {'perfect':>8} {'read':>6} {'kept':>6} "
               f"{'checked':>8}")
OVER_STEPS: Final = ((1, "STEPS1", ("STEPS1",)), (2, "MAIN", ("MAIN", "REPEAT")), (4, "STEPS4", ("STEPS4",)),
                     (8, "STEPS8", ("STEPS8",)))


def distance(p: dict[str, float], q: dict[str, float]) -> float:
    """The total variation distance of two sets of shares."""
    return 0.5 * sum(abs(p.get(k, 0.0) - q.get(k, 0.0)) for k in p.keys() | q.keys())


def load_counts(source: str) -> dict[str, dict[str, int]]:
    """The counts of a file written by compare.py, from a path or a link that begins with https://."""
    if source.startswith("https://"):
        with urlopen(source, timeout=30) as answer:
            return json.load(answer)
    return json.loads(Path(source).read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class Reading:
    """The counts of one job as shares, raw and among the keys with the excitations the job started with."""

    counts: dict[str, int]
    excitations: int = 1

    @property
    def shots(self) -> int:
        """All the shots."""
        return sum(self.counts.values())

    @property
    def raw(self) -> dict[str, float]:
        """The share of each key."""
        return {key: n / self.shots for key, n in self.counts.items()}

    @property
    def kept(self) -> float:
        """The share of shots that keep the excitations: every other key is a machine error, not a Trotter error."""
        return sum(v for key, v in self.raw.items() if key.count("1") == self.excitations)

    @property
    def post(self) -> dict[str, float]:
        """The share of each key that keeps the excitations, among those."""
        kept = self.kept
        return {key: v / kept for key, v in self.raw.items() if key.count("1") == self.excitations} if kept else {}


@dataclass(frozen=True, slots=True)
class Run:
    """The jobs of a folder, with what came back for each."""

    jobs: dict[str, dict]
    read: dict[str, Reading]

    @classmethod
    def of(cls, folder: str, source: str | None = None) -> "Run":
        """A folder and its results.json; the counts of `source`, if given, take the place of the same jobs."""
        manifest = json.loads((Path(folder) / "manifest.json").read_text(encoding="utf-8"))
        jobs = {job["name"]: job for job in manifest["jobs"]}
        counts = {**load_counts(str(Path(folder) / "results.json")), **(load_counts(source) if source else {})}
        read = {name: Reading(counts[name], job["excitations"]) for name, job in jobs.items() if name in counts}
        return cls(jobs, read)

    def _row(self, name: str) -> str:
        job, read = self.jobs[name], self.read[name]
        key = job["key"]
        return (f"{name:<11} {job['time']:>4} {job['steps']:>2} {job['two_qubit']:>3} {key:>4} "
                f"{job['text_shares'][key]:>8.3f} {read.raw.get(key, 0):>6.3f} {read.kept:>6.3f} "
                f"{read.post.get(key, 0):>8.3f}")

    def table(self) -> str:
        """One line for each job that came back."""
        return "\n".join([HEAD, *(self._row(name) for name in self.jobs if name in self.read)])

    def _beside(self, name: str, emulators: dict[str, dict[str, dict[str, float]]]) -> str:
        job, key = self.jobs[name], self.jobs[name]["key"]
        read = f"{self.read[name].raw.get(key, 0):>8.3f}" if name in self.read else ""
        others = "".join(f"{shares[name].get(key, 0.0):>9.6f} " for shares in emulators.values())
        return f"{name:<11} {key:>4} {job['text_shares'][key]:>9.6f} {others}{read}"

    def beside(self, emulators: dict[str, dict[str, dict[str, float]]]) -> str:
        """For the key of each job: the perfect share by our emulator, by each emulator named, and the share read."""
        head = f"{'job':<11} {'key':>4} {'ours':>9} " + "".join(f"{label:>9} " for label in emulators)
        return "\n".join([f"{head}{'machine':>8}", *(self._beside(name, emulators) for name in self.jobs)])

    def beside_qrisp(self, qrisp: dict[str, dict[str, float]]) -> str:
        """The same with Qrisp's emulator alone, as the tutorial first printed it."""
        return self.beside({"Qrisp": qrisp})

    def over_time(self) -> dict[float, list[Reading]]:
        """The readings at each time, for the chart of the curves."""
        read = self.read
        return {0.0: [read["CONTROL"]], T / 2: [read["HALF"]], T: [read["MAIN"], read["REPEAT"]],
                2 * T: [read["BACK"]]}

    def over_steps(self) -> list[tuple[int, int, float, list[Reading]]]:
        """For each number of steps: N, the two-qubit gates, the perfect share of 100, and the readings."""
        return [(n, self.jobs[name]["two_qubit"], self.jobs[name]["text_shares"]["100"], [self.read[k] for k in keys])
                for n, name, keys in OVER_STEPS]
