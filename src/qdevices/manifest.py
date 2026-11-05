"""Read and check a manifest; a key the app does not own is copied to the start line, as a fact of the experiment."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final

from .errors import Refused
from .values import is_int, regular_file, sha256_hex

FORMAT: Final = "qdevices/1"
NAME: Final = re.compile(r"[A-Za-z0-9_-]+")
SHA: Final = re.compile(r"[0-9a-f]{64}")
OWN: Final = frozenset({"format", "site", "machine", "project", "run", "jobs"})    # and the route keys of the sites
JOB_KEYS: Final = ("order", "name", "file", "sha256", "shots")
MOST_SHOTS: Final = 10 ** 9           # far above any site; the seconds and sums of shots stay finite


class ManifestError(Refused):
    """The manifest cannot be used. Nothing is sent."""


def shot_problem(value: object) -> str | None:
    """What is wrong with the shots of a job, in the words of a problem of the manifest; None for good shots."""
    if not (is_int(value) and value >= 1):
        return "shots must be a whole number of 1 or more"
    return f"shots must be at most {MOST_SHOTS:,}" if value > MOST_SHOTS else None


def takes_shots(value: object) -> bool:
    """True for the shots of a job that a manifest takes: a whole number from 1 to MOST_SHOTS."""
    return shot_problem(value) is None


def _no_file(path: Path) -> str | None:
    """Why there is no file to read at a path, or None; a folder that cannot be searched fails the test itself."""
    try:
        return None if regular_file(path) else f"there is no file {path}"
    except OSError as exc:
        return f"the file {path} cannot be read: {type(exc).__name__}"


@dataclass(slots=True, kw_only=True)
class _Reader:
    """The read of one manifest: each step adds its problems to one list, in the order of the manifest."""

    path: Path
    sites: dict
    problems: list[str] = field(default_factory=list)

    def read(self) -> tuple[dict | None, list[str]]:
        """The manifest and its problems; no manifest when its head or its list of jobs cannot be used."""
        loaded = self._raw()
        if loaded is None:
            return None, self.problems
        data, raw = loaded
        head = self._head(raw)
        if head is None:
            return None, self.problems
        site, run = head
        jobs = self._jobs(raw.get("jobs"), self.sites[site].options)
        if jobs is None:
            return None, self.problems
        routes = tuple(dict.fromkeys(key for cls in self.sites.values() for key, _ in cls.profile.route_keys))
        manifest = {"path": self.path, "folder": self.path.parent, "sha256": sha256_hex(data), "site": site,
                    "run": run, "machine": raw.get("machine"), "project": raw.get("project"),
                    **{key: raw.get(key) for key in routes},        # of every site, None where not given
                    "extra": {k: v for k, v in raw.items() if k not in OWN and k not in routes}}
        manifest["jobs"] = [self._entry(job) for job in jobs]
        return manifest, self.problems

    def _raw(self) -> tuple[bytes, dict] | None:
        """The bytes of the manifest and the JSON object they hold; None when they hold none."""
        try:
            data = self.path.read_bytes()
            raw = json.loads(data)
        except (OSError, ValueError, RecursionError) as exc:          # RecursionError: nested too deep
            self.problems.append(f"{self.path} cannot be read as JSON: {type(exc).__name__}")
            return None
        if not isinstance(raw, dict):
            self.problems.append(f"{self.path} is not a JSON object")
            return None
        return data, raw

    def _head(self, raw: dict) -> tuple[str, object] | None:
        """The site and the run of the manifest; None for a site the app does not know."""
        if raw.get("format") != FORMAT:
            self.problems.append(f'"format" must be "{FORMAT}"')
        site = raw.get("site")
        if not isinstance(site, str) or site not in self.sites:
            self.problems.append(f'"site" must be one of {", ".join(self.sites)}')
            return None
        texts = ("machine", "project", *(key for key, _ in self.sites[site].profile.route_keys))
        for key in texts:
            if not isinstance(raw.get(key), str) or not raw.get(key):
                self.problems.append(f'"{key}" must be a text')
        run = raw.get("run", self.path.parent.resolve().name)
        if not isinstance(run, str) or not NAME.fullmatch(run):
            self.problems.append(f'the run name {run!r} is not of [A-Za-z0-9_-]+: give "run" in the manifest')
        return site, run

    def _jobs(self, jobs: object, options: dict) -> list[dict] | None:
        """The jobs of the manifest, each checked; None when they are not a list of one or more objects."""
        if not isinstance(jobs, list) or not jobs or not all(isinstance(j, dict) for j in jobs):
            self.problems.append('"jobs" must be a list of objects, one or more')
            return None
        orders = [j.get("order") for j in jobs]
        if not all(map(is_int, orders)) or orders != list(range(1, len(jobs) + 1)):    # 1.0 == 1, yet not folded
            self.problems.append("the orders must be 1 to N in sequence, without gaps")
        for index, job in enumerate(jobs, 1):
            self._job(job, f"job {index}", options)
        return jobs

    def _job(self, job: dict, where: str, options: dict) -> None:
        """The problems of one job, named by its place in the list."""
        missing = [f"{where}: no {key}" for key in JOB_KEYS if key not in job]
        if missing:
            self.problems.extend(missing)
            return
        if not isinstance(job["name"], str) or not NAME.fullmatch(job["name"]):
            self.problems.append(f"{where}: the name {job['name']!r} is not of [A-Za-z0-9_-]+")
        file, folder = job["file"], self.path.parent
        if not isinstance(file, str) or Path(file).name != file or file in (".", ".."):
            self.problems.append(f"{where}: the file {file!r} must be a file name next to the manifest")
        elif (missing := _no_file(folder / file)) is not None:
            self.problems.append(f"{where}: {missing}")
        if not isinstance(job["sha256"], str) or not SHA.fullmatch(job["sha256"]):
            self.problems.append(f"{where}: sha256 is not 64 lower-case hex digits")
        if (problem := shot_problem(job["shots"])) is not None:
            self.problems.append(f"{where}: {problem}")
        self._options(job.get("options", {}), where, options)

    def _options(self, given: object, where: str, options: dict) -> None:
        """The problems of the options of one job against the options of its site."""
        if not isinstance(given, dict):
            self.problems.append(f"{where}: options must be an object")
            return
        for key, value in given.items():
            if key not in options:
                self.problems.append(f"{where}: the option {key!r} is not one of this site "
                                     f"({', '.join(sorted(options)) or 'none'})")
            elif not isinstance(value, options[key]):
                self.problems.append(f"{where}: the option {key!r} has the wrong type")

    def _entry(self, job: dict) -> dict:
        """A job as the manifest gives it, its options copied, and its text while no problem is found."""
        given = job.get("options") or {}
        entry = {**job, "options": dict(given) if isinstance(given, dict) else given}     # not an object: a problem
        file = self.path.parent / str(job.get("file", ""))
        if not self.problems and _no_file(file) is None:
            try:
                entry["text"] = file.read_bytes()
            except OSError as exc:
                self.problems.append(f"order {job['order']}: the file {file} cannot be read: {type(exc).__name__}")
                return entry
            digest = sha256_hex(entry["text"])
            if digest != job["sha256"]:
                self.problems.append(f"order {job['order']}: the SHA-256 of {job['file']} is {digest}, the "
                                     f"manifest has {job['sha256']}")
        return entry


def read(path: Path, sites: dict) -> tuple[dict | None, list[str]]:
    """The manifest and its problems. `sites` maps a site name to its class (for its options and route keys)."""
    return _Reader(path=Path(path), sites=sites).read()


def load(path: Path, sites: dict) -> dict:
    """The manifest, or ManifestError with all its problems."""
    manifest, problems = read(path, sites)
    if problems:
        raise ManifestError("; ".join(problems))
    return manifest


def file_bytes(manifest: dict, job: dict) -> bytes:
    """The file of a job as it is on disk now, checked against the manifest again before it is sent."""
    data = (manifest["folder"] / job["file"]).read_bytes()
    if sha256_hex(data) != job["sha256"]:
        raise ManifestError(f"order {job['order']} ({job['name']}): {job['file']} has changed since the "
                            "manifest was written; nothing is sent")
    return data
