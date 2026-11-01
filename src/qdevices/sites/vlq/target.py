"""Where a VLQ job goes: LEXIS membership and resource, HEAppE project, templates and queues. It only reads."""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Self

from ...values import is_int
from ..base import Channel, SiteError
from .wire import JobKind


@contextmanager
def _listing() -> Iterator[None]:
    """A listing of LEXIS or HEAppE in a form the app does not read: a SiteError of the read, not of the program."""
    try:
        yield
    except (AttributeError, KeyError, TypeError, IndexError) as exc:
        raise SiteError(f"a listing of LEXIS or HEAppE cannot be read: {type(exc).__name__}: {exc}",
                        step="read") from None


def _walltime(value: object) -> int | None:
    if value is not None and not is_int(value):          # read here, so no job request meets it
        raise TypeError(f"MaxWalltime is a {type(value).__name__}, not a whole number")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class Target:
    """The HEAppE project of a LEXIS resource, with its enabled templates and its queues."""

    resource: dict
    project_id: int
    project_name: str | None
    templates: dict          # template name -> id
    queues: dict             # queue name -> cluster, node type, walltime, transfer method, formula

    @classmethod
    def of(cls, resource: dict, project: dict, clusters: Iterable[dict]) -> Self:
        """The target of a resource in its HEAppE project, with the templates and queues of the cluster listing."""
        accounting, templates, queues = resource["resource_name"], {}, {}
        # Each value is read before its key (assignments, not comprehensions): a malformed listing names Id first.
        for cluster in clusters:
            for node in cluster.get("NodeTypes") or []:
                enabled = (template for node_project in node.get("Projects") or []
                           if node_project.get("AccountingString") == accounting
                           for template in node_project.get("CommandTemplates") or [] if template.get("IsEnabled"))
                for template in enabled:
                    templates[template["Name"]] = template["Id"]
                queues[node["Name"]] = {"cluster_id": cluster["Id"], "node_type_id": node["Id"],
                                        "max_walltime": _walltime(node.get("MaxWalltime")),
                                        "file_transfer_method_id": node.get("FileTransferMethodId"),
                                        "formula": ((node.get("Accounting") or [{}])[0]).get("Formula")}
        return cls(resource=resource, project_id=project["Id"], project_name=project.get("Name"),
                   templates=templates, queues=queues)

    def absent(self, kinds: tuple[JobKind, ...]) -> list[str]:
        """The queues, then the templates, of these kinds of job that HEAppE does not list for this token."""
        return ([kind.queue for kind in kinds if kind.queue not in self.queues]
                + [kind.template for kind in kinds if kind.template not in self.templates])


@dataclass(slots=True, kw_only=True)
class Lookup:
    """The reads of LEXIS and HEAppE that find where the jobs of a site go; the target is found once and kept."""

    userorg: Channel
    heappe: Channel
    lexis_project: str | None
    resource_name: str | None
    kinds: tuple[JobKind, ...]
    _target: Target | None = field(default=None, init=False)

    def member(self) -> dict | None:
        """The LEXIS project row of the token's user, or None when the user is not a member."""
        rows = self.userorg.answer("GET", "/Project", step="read", params={"ProjectShortName": self.lexis_project})
        with _listing():
            found = (row for row in rows or [] if isinstance(row, dict) and row.get("ShortName") == self.lexis_project)
            return next(found, None)

    def target(self) -> Target:
        """The target, found at the first call; a SiteError at each call while HEAppE lacks a queue or template."""
        if self._target is None:
            with _listing():
                self._target = self._discover()
        absent = self._target.absent(self.kinds)
        if absent:
            raise SiteError(f"HEAppE does not list {', '.join(absent)} for this token", step="read")
        return self._target

    def dry_run(self, target: Target, kind: JobKind) -> Any:
        """The answer of HEAppE to a dry run of one node for a minute on the queue of a kind, which makes no job."""
        queue = target.queues[kind.queue]
        return self.heappe.answer("POST", "/JobManagement/DryRunJob", step="read",
                                  json={"ProjectId": target.project_id, "ClusterNodeTypeId": queue["node_type_id"],
                                        "Nodes": 1, "TasksPerNode": 1, "WallTimeInMinutes": 1})

    def _discover(self) -> Target:
        resource = self._resource()
        accounting = resource["resource_name"]
        projects = self.heappe.answer("GET", "/UserAndLimitationManagement/ProjectsForCurrentUser", step="read") or []
        chosen = next((p["Project"] for p in projects if isinstance(p, dict)
                       and (p.get("Project") or {}).get("AccountingString") == accounting), None)
        if chosen is None:
            raise SiteError(f"HEAppE lists no project with the accounting string {accounting!r}", step="read")
        clusters = self.heappe.answer("GET", "/ClusterInformation/ListAvailableClusters", step="read") or []
        return Target.of(resource, chosen, clusters)

    def _resource(self) -> dict:
        rows = self.userorg.answer("GET", "/ProjectResource", step="read",
                                   params={"ProjectShortName": self.lexis_project})
        for row in rows or []:
            if not isinstance(row, dict) or row.get("Name") != self.resource_name:
                continue
            for assignment in row.get("Assignments") or []:          # the first assignment
                return {"resource_name": row["Name"], "project_resource_id": assignment.get("ProjectResourceId"),
                        "location_name": assignment.get("LocationName"),
                        "allocation_amount": assignment.get("AllocationAmount")}
        raise SiteError(f"LEXIS lists no resource {self.resource_name!r} on the project {self.lexis_project!r}",
                        step="read")
