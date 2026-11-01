"""The HEAppE calls of a VLQ job: CreateJob, the uploads, SubmitJob, the state, and the downloads.

The job's environment is never written to a record; each password joins the token filter before its CreateJob.
"""

import base64
from dataclasses import dataclass, field

from .. import pickle_reader
from ..base import Channel, SiteError, cut
from .envelope import Envelope
from .target import Target
from .wire import PROGRESS_FILE, TEXT, TOKEN_FILE, JobKind


def _first_task(tasks: object) -> object:
    """The id of the first task of a list of tasks, or None where the answer gives none of a usable type."""
    first = tasks[0] if isinstance(tasks, list) and tasks else None
    found = first.get("Id") if isinstance(first, dict) else None
    return found if isinstance(found, (int, str)) else None


@dataclass(frozen=True, slots=True, kw_only=True)
class _CreatedJob:
    """A job made by CreateJob: its id, its first task, and the envelope of its token."""

    id: object
    task: object
    envelope: Envelope = field(repr=False)


class HeappeJobs:
    """The job calls of one HEAppE client, for one LEXIS project and one target."""

    def __init__(self, client: Channel, token: str, lexis_project: str | None) -> None:
        self.client, self.token, self.lexis_project = client, token, lexis_project
        self.passwords: list[str] = []
        self.tasks: dict = {}         # job id -> its task id

    def create(self, target: Target, kind: JobKind, step: str, extra: dict | None = None) -> _CreatedJob:
        """CreateJob of one kind of job; both forms of its new password join `passwords` before the request."""
        queue = target.queues[kind.queue]
        envelope = Envelope.new()
        self.passwords += [envelope.password, envelope.encoded]
        env = {"Q_COMMAND": kind.command, "USER_JWT_PWD": envelope.encoded, "LEXIS_PROJECT": self.lexis_project,
               "LEXIS_PROJECT_RESOURCE_ID": target.resource["project_resource_id"], **(extra or {})}
        body = {"JobSpecification": {
            "Name": kind.name, "ProjectId": target.project_id, "ClusterId": queue["cluster_id"],
            "FileTransferMethodId": queue["file_transfer_method_id"],
            "EnvironmentVariables": [{"Name": k, "Value": v} for k, v in env.items()],
            "Tasks": [{"Name": "quantum_task", "MinCores": kind.cores, "MaxCores": kind.cores,
                       "WalltimeLimit": min(kind.walltime, queue["max_walltime"] or kind.walltime),
                       "ProgressFile": PROGRESS_FILE, "LogFile": PROGRESS_FILE,
                       "ClusterNodeTypeId": queue["node_type_id"],
                       "CommandTemplateId": target.templates[kind.template], "TemplateParameterValues": []}]}}
        info = self.client.answer("POST", "/JobManagement/CreateJob", step=step, json=body, fields=True)
        task = _first_task((info or {}).get("Tasks") or [])
        if not isinstance(info, dict) or not isinstance(info.get("Id"), (int, str)) or task is None:
            raise SiteError("the answer to CreateJob has no job with a task", body=cut(info), step=step)
        self.tasks[info["Id"]] = task
        return _CreatedJob(id=info["Id"], task=task, envelope=envelope)

    def upload(self, job_id: object, task: object, filename: str, content: bytes, media: str, step: str) -> None:
        """One file of a media type into the folder of a job, which the answer must show as taken."""
        reply = self.client.answer("POST", "/FileTransfer/UploadFilesToJobExecutionDir", step=step,
                                   params={"JobId": job_id, "TaskId": task},
                                   files={"files": (filename, content, media)})
        if not isinstance(reply, list) or not any(e.get("FileName") == filename and e.get("Succeeded")
                                                  for e in reply if isinstance(e, dict)):
            raise SiteError(f"the service did not take the file {filename}", body=cut(reply), step=step)

    def upload_token(self, job: _CreatedJob, step: str) -> None:
        """The token in the envelope of its job, as the file the job reads."""
        self.upload(job.id, job.task, TOKEN_FILE, job.envelope.seal(self.token), TEXT, step)

    def submit(self, job_id: object, step: str) -> None:
        """SubmitJob: the request that puts a job made by CreateJob in its queue; only its HTTP status is read."""
        self.client.request("PUT", "/JobManagement/SubmitJob", step=step, json={"CreatedJobInfoId": job_id})

    def info(self, job_id: object, step: str) -> dict:
        """The info of a job, which must give its state as an integer; its first task is kept for the downloads."""
        info = self.client.answer("GET", "/JobManagement/CurrentInfoForJob", step=step,
                                  params={"SubmittedJobInfoId": job_id})
        if not isinstance(info, dict) or not isinstance(info.get("State"), int):
            raise SiteError("the answer has no state", body=cut(info), step=step)
        task = _first_task(info.get("Tasks"))
        if task is not None:
            self.tasks[job_id] = task
        return info

    def download(self, job_id: object, name: str, step: str) -> bytes:
        """One file of the folder of a job: the bytes of its base64 text, within the size limit of the pickle reader."""
        task = self.tasks.get(job_id)
        if task is None:
            self.info(job_id, step)
            task = self.tasks.get(job_id)
        raw = self.client.answer("POST", "/FileTransfer/DownloadFileFromCluster", step=step,
                                 json={"SubmittedJobInfoId": job_id, "RelativeFilePath": f"/{job_id}/{task}/{name}"})
        try:
            if isinstance(raw, str) and len(raw) <= pickle_reader.MAX_BYTES * 4 // 3 + 4:
                return base64.b64decode(raw)
        except ValueError:                        # binascii.Error, or a text that is not ASCII
            pass
        raise SiteError(f"the download of {name} is not a text of base64 within the size limit", step=step)
