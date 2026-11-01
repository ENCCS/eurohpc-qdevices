"""The VLQ site class over HEAppE and LEXIS UserOrg: SubmitJob only in `submit` and `prepare`, never on a resume."""

import pickle
from typing import TYPE_CHECKING, Self

from ...qasm import Qasm
from ..base import Site, SiteError
from ..facts import Profile
from ..pickle_reader import PickleRefused
from ..protocol import JobState, Note, Refusal
from . import wire
from .heappe import HeappeJobs
from .init_job import InitJob
from .results import ResultsFile
from .status import StatusFile
from .target import Lookup

if TYPE_CHECKING:
    import httpx

    from ...clock import Clock, Sleep


class VLQ(Site):
    """VLQ at IT4I: for each order an init job, then the metered job, each made by CreateJob and sent by SubmitJob."""

    name = "vlq"
    token_env = "LEXIS_TOKEN"
    profile = Profile(
        title="VLQ", operator="IT4Innovations", login=wire.LOGIN, billing=wire.BILLING, older_machines=("VLQ",),
        config_keys=(wire.LEXIS_PROJECTS_KEY,), member_key="lexis_project", status_rows=tuple(wire.STATUS_ROWS.items()),
        route_keys=(("lexis_project", "LEXIS project"), ("resource", "resource")), secret_patterns=wire.SECRET_PATTERNS,
        numeric_ids=True, configuring_state=wire.HeappeState.of(wire.CONFIGURING).name, token_label="LEXIS token",
        token_expiry=wire.token_expiry, token_min_seconds=30 * 60, token_waits=2,  # a wait for each of the two jobs
        usage_note="VLQ init jobs book classical node time only.")
    init_kind, run_kind = wire.INIT_KIND, wire.RUN_KIND      # the two jobs of an order, in the order made
    native = wire.NATIVE                  # the gates a text may use, as the site does not compile
    status_address = wire.STATUS
    addresses = (wire.HEAPPE, wire.USERORG, status_address)
    made_step = "created"         # written after CreateJob, before the uploads
    submit_step = "uploaded"      # written after the uploads, just before SubmitJob
    default_machine = "VLQ"
    refusal = Refusal(step=f"upload:{wire.CIRCUIT_FILE}",    # a 4xx to the circuit upload, before SubmitJob: no job ran
                      codes=frozenset(range(400, 500)) - frozenset(wire.NOT_A_REFUSAL))
    config_problems = staticmethod(wire.lexis_problems)      # the LEXIS project of a manifest, in lexis_projects

    def __init__(self, token: str, machine: str | None = None, *, lexis_project: str | None = None,
                 resource: str | None = None, clock: "Clock | None" = None, sleep: "Sleep | None" = None,
                 wait_seconds: float = 900.0, transport: "httpx.BaseTransport | None" = None) -> None:
        super().__init__(token, machine, transport=transport)
        self.lexis_project, self.resource_name = lexis_project, resource
        self.clock, self.sleep, self.wait_seconds = clock, sleep, wait_seconds
        auth = {"Authorization": f"Bearer {token}"}       # no Content-Type: it would spoil the multipart uploads
        userorg = self.client(wire.USERORG, auth, timeout=45.0)
        self.jobs = HeappeJobs(self.client(wire.HEAPPE, auth, timeout=120.0), token, lexis_project)
        self._status_file = StatusFile(self, self.status_address)     # its own client, with no Authorization header
        self._lookup = Lookup(userorg=userorg, heappe=self.jobs.client, lexis_project=lexis_project,
                              resource_name=resource, kinds=(self.init_kind, self.run_kind))

    @classmethod
    def from_manifest(cls, manifest: dict, token: str, *, clock: "Clock", sleep: "Sleep", site_config: dict,
                      transport: "httpx.BaseTransport | None" = None) -> Self:
        """A VLQ site for a manifest: its machine, LEXIS project and resource, and wait_seconds of the site config."""
        return cls(token, manifest.get("machine"), lexis_project=manifest.get("lexis_project"),
                   resource=manifest.get("resource"), clock=clock, sleep=sleep,
                   wait_seconds=float(site_config["wait_seconds"]), transport=transport)

    def read(self) -> dict:
        """One read of the machine, which makes no job. It starts with the status file, whose failure it keeps."""
        out = {"machine": self.machine, "lexis_project": self.lexis_project, "member": False,
               "status": self._status_file.read()}
        if self._lookup.member() is None:
            return out
        target = self._lookup.target()
        dry = self._lookup.dry_run(target, self.run_kind)      # sent before the templates are sorted
        queues = {n: {"max_walltime": q["max_walltime"], "formula": q["formula"]} for n, q in target.queues.items()}
        return {**out, "member": True, "resource": target.resource, "project_name": target.project_name,
                "templates": sorted(target.templates, key=str), "queues": queues, "dry_run": dry}

    def prepare(self, job: dict, note: Note) -> dict:
        """The init job of an order (init_job.py), and the check of the text against its table. No device time."""
        init = InitJob(jobs=self.jobs, target=self._lookup.target(), clock=self.clock, sleep=self.sleep,
                       wait_seconds=self.wait_seconds, poll_seconds=self.poll_seconds, kind=self.init_kind)
        return init.run(note, Site.text_of(job))

    def submit(self, job: dict, note: Note, prepared: dict) -> int:
        """The metered job: CreateJob, the token, the circuit and the files, then SubmitJob. The answer is its id."""
        created = self.jobs.create(self._lookup.target(), self.run_kind, "create")
        note(self.made_step, job=created.id, task=created.task)
        self.jobs.upload_token(created, f"upload:{wire.TOKEN_FILE}")
        uploads = [(wire.CIRCUIT_FILE, job["text"], wire.TEXT),
                   (wire.RUN_KWARGS_FILE, pickle.dumps({"shots": job["shots"]}), wire.BINARY),
                   *((name, prepared["artefacts"][name], wire.BINARY) for name in wire.ARTEFACTS)]
        for filename, content, media in uploads:
            self.jobs.upload(created.id, created.task, filename, content, media, f"upload:{filename}")
        note(self.submit_step, job=created.id)
        self.jobs.submit(created.id, "submit")
        return created.id

    def status(self, job_id: object) -> JobState:
        """The state of a job: the name of its HEAppE number, and the number as its code."""
        s = wire.HeappeState.of(self.jobs.info(job_id, "status")["State"])
        return JobState(state=s.name, final=s.final, ok=s.ok, configuring=s.configuring, code=s.code)

    def result(self, job_id: object) -> dict:
        """The counts and the device seconds, which a result must give, and the calibration set, or None."""
        files = {name: self.jobs.download(job_id, name, "result") for name in wire.RESULT_FILES}
        try:
            found = ResultsFile.parse(files[wire.RESULTS_FILE])
            seconds = ResultsFile.device_seconds(files[wire.JOB_FILE])
        except PickleRefused as exc:
            raise SiteError(f"a result file cannot be read: {exc}", step="result") from None
        if not found.counts or (seconds is None and not ResultsFile.names_seconds(files[wire.JOB_FILE])):
            raise SiteError("the result files do not give the counts and the device seconds; the job is "
                            "finished, a resume reads them again", step="result")
        return {"counts": found.counts, "seconds": seconds, "success": found.success, "returned_shots": found.shots,
                "calibration_set": found.calibration_set, "files": wire.digests(files)}

    def logs(self, job_id: object) -> dict:
        """The end of each log file of a failed job, or "<unavailable>" for a file that cannot be read."""
        out = {}
        for name in wire.LOG_FILES:
            try:
                out[name] = self.jobs.download(job_id, name, "logs").decode("utf-8", "replace")[-wire.LOG_CHARACTERS:]
            except SiteError:
                out[name] = "<unavailable>"
        return out

    def token_seconds_left(self) -> float | None:
        """The seconds before the LEXIS token expires, by its claim, or None where they cannot be read."""
        expiry = wire.token_expiry(self._token)
        return None if expiry is None or self.clock is None else expiry - self.clock.utc().timestamp()

    def secrets(self) -> list[str]:
        """The token, then each password made for a job, raw and in base64, in the order made."""
        return [*super().secrets(), *self.jobs.passwords]

    @classmethod
    def validate(cls, job: dict, read: dict | None) -> list[str]:
        """The problems of a text for VLQ: OpenQASM 3, native gates only, r and move declared, qubits of the read."""
        text = Site.text_of(job)
        parsed = Qasm.parse(text)
        problems = [] if "OPENQASM 3" in text else ["the file is not an OpenQASM 3 text"]
        used, declared = parsed.gate_names, parsed.declared_gates
        if outside := sorted(used - cls.native):
            problems.append(f"the gates {outside} are not native on VLQ ({', '.join(sorted(cls.native))}); "
                            "the site does not compile")
        problems += [f"the text uses {gate} and does not declare it (gate {gate} ... {{ gphase(0); }})"
                     for gate in ("r", "move") if gate in used and gate not in declared]
        return problems + parsed.qubit_problems(read)
