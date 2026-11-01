"""The opening of a record again: its resume line, its cut lines, and the checks of a resume that sends."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from .. import __version__
from .. import record as records
from ..errors import Refused
from ..finder import AppRecords
from ..ledger import Ledger
from .opening import Opened, Opening
from .preflight import SiteScan
from .rulesfile import RulesFile

ID_IN_LINE: Final = re.compile(r'"(?:id|job)":\s*("(?:[^"\\]|\\.)*("?)|-?\d[\d.eE+-]*)')    # 2: the closing quote


def cut_entry(number: int, text: str) -> dict:
    """A cut line for the resume line: its number, its first 120 characters, and any job id it holds."""
    entry = {"line": number, "text": text[:120]}
    found = ID_IN_LINE.search(text)
    if found is None:
        return entry
    value = found.group(1)
    if value.startswith('"'):
        closed = found.group(2) == '"'              # not the quote of an escape at the cut
        value, cut = (value[1:-1] if closed else value[1:]), not closed
    else:
        cut = found.end() == len(text)
    return {**entry, "job_id": value, "job_id_may_be_cut": cut} if value else entry


@dataclass(kw_only=True)
class Resume(Opening):
    """The record at a path, opened again with its resume line; Refused when this call may not go on with it."""

    path: Path

    def _open(self, site_scan: SiteScan) -> Opened:
        path = Path(self.path)
        prior, cut, start = self._read(path)
        self._may_go_on(path, start)
        rules_fields, note = self.rules_file.resume_fields(path, start, prior, new_rules=self.new_rules,
                                                           sending=self.sending)
        rec = self.record(path)
        cuts = [cut_entry(n, t) for n, t in cut]
        line = rec.write("resume", max_order=self.max_order, host=self.host, version=__version__,
                         cut_lines=cuts, **rules_fields)
        known, held = RulesFile.held_by(start, [*prior, line])     # no line sets one: the file of this call
        return Opened(rec, prior, site_scan, (held if known else self.rules_file).path, lambda: self._say(cuts, note))

    def _read(self, path: Path) -> tuple[list[dict], list, dict]:
        try:
            prior, cut = records.RecordLines.read(path)
        except records.RecordError as exc:
            raise Refused(str(exc)) from None
        start = Ledger(prior).start
        if start is None:
            raise Refused(f"{path} has no start line")
        if start.get("manifest_sha256") != self.man["sha256"] or start.get("files") != self.files():
            raise Refused(f"{path} was made with another manifest or other files; it cannot be continued")
        return prior, cut, start

    def _may_go_on(self, path: Path, start: dict) -> None:
        if self.sending:
            problems = self._copy_problems(path, start)
            if problems:
                raise Refused(f"{path} sends nothing: {'; '.join(problems)}. It may be a copy, and a copy and its "
                              "record would each send the same orders. Give --resume without --max-order to "
                              "collect only")
        elif path.resolve().parent != self.run_dir.resolve():
            self.say(f"NOTE: {path} is not in the records folder; it is collected only")

    def _say(self, cuts: list[dict], note: str | None) -> None:
        for c in cuts:
            self.say(f"NOTE: line {c['line']} of the record is cut and is not read: {c['text']}")
            if "job_id" in c:
                self.say(f"NOTE: line {c['line']} holds the job id {c['job_id']}"
                         + ("; the id may be cut, as the line ends in it" if c["job_id_may_be_cut"] else ""))
        if note:
            self.say(f"NOTE: {note}")

    def _copy_problems(self, path: Path, start: dict) -> list[str]:
        """Why a record may not send: not the newest of its run folder, not the file or host that made it."""
        real = path.resolve()
        folder = self.run_dir.resolve()
        info = real.stat()
        problems = []
        if real.parent != folder or not records.NAME.fullmatch(real.name):
            problems.append(f"it is not a record of the run folder {folder}")
        elif AppRecords(folder).newest() != real:
            problems.append(f"it is not the newest record of {folder}")
        if start.get("record") != self._identity(real, info):
            problems.append("its path, device or inode is not the one of its start line")
        if start.get("host") != self.host:
            problems.append(f"it was started on the host {start.get('host')!r}, this is {self.host!r}")
        return problems
