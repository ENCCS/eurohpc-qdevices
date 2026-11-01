"""The public status file of VLQ, read once in each read of the machine, through a client with no header.

A failed read keeps a short reason and stops nothing; the rule site_status (rules.py) decides on the flags.
"""

from ...values import ANSWER_DEPTH, too_deep
from ..base import Site, SiteError
from .wire import STATUS_ROWS


class StatusFile:
    """The status file at an address, read by a client of its own with no header, so no token goes to it."""

    def __init__(self, site: Site, address: str) -> None:
        self.folder, self.file = address.rsplit("/", 1)
        self.client = site.client(self.folder, {}, timeout=30.0)

    def read(self) -> dict:
        """{"flags", "timestamp", "error"}: the flags and the time stamp of the file, or why it was not read."""
        answer = self._answer()
        if isinstance(answer, str):
            return {"flags": None, "timestamp": None, "error": answer}
        return {"flags": {name: answer.get(name) for name in STATUS_ROWS}, "timestamp": answer.get("timestamp"),
                "error": None}

    def _answer(self) -> dict | str:
        # the JSON object of the file, or why it was not read
        try:
            response = self.client.request("GET", self.file, step="status_file")
        except SiteError as exc:
            return str(exc)
        if response.status_code != 200:
            return f"HTTP {response.status_code} to GET {self.file}"
        try:
            answer = response.json()
        except (ValueError, RecursionError):
            return "the answer is not JSON"
        if too_deep(answer):
            return f"the answer is not JSON of at most {ANSWER_DEPTH} levels"
        return answer if isinstance(answer, dict) else "the answer is not a JSON object"
