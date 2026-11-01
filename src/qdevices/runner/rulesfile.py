"""The rules file of a record: the one a resume is held to, and the rules fields of a resume line."""

from dataclasses import dataclass
from typing import Any, Self

from ..errors import Refused
from ..screen import quoted


@dataclass(frozen=True, slots=True, eq=False)
class RulesFile:
    """What a rules_file field holds, as it is: None, a path and SHA-256, or anything an older record holds."""

    value: Any

    @property
    def sha256(self) -> str | None:
        """Its SHA-256; None for no rules file or a value that is not a file."""
        return self.value.get("sha256") if isinstance(self.value, dict) else None

    @property
    def path(self) -> str | None:
        """The path to give with --rules; None for no rules file."""
        return self.value.get("path") if self.sha256 is not None else None

    def __str__(self) -> str:
        if self.sha256 is None:
            return "no rules file"
        return f"{self.value.get('path')} (SHA-256 {self.value['sha256']})"

    @classmethod
    def held_by(cls, start: dict, prior: list[dict]) -> tuple[bool, Self]:
        """Whether a line of the record sets the rules file it is held to, and that file."""
        resumes = [e for e in prior if e.get("event") == "resume" and "rules_file" in e]
        renewed = [e for e in resumes if e.get("new_rules") is True]
        sent = [e for e in resumes if e.get("max_order") is not None]
        first = start if "rules_file" in start or not sent else sent[0]     # an older start line has none
        line = renewed[-1] if renewed else first
        return "rules_file" in line, cls(line.get("rules_file"))

    def resume_fields(self, path, start: dict, prior: list[dict], *, new_rules: bool,
                      sending: bool) -> tuple[dict, str | None]:
        """The rules fields of a resume line with this file and a note to print; Refused for one that may not send."""
        known, before = self.held_by(start, prior)
        fields = {"rules_file": self.value, "new_rules": new_rules}
        if known and new_rules:
            fields["rules_before"] = before.value
        if not known:
            older = "the start line of the record has no rules field (an older version of the app made it)"
            if sending or new_rules:
                note = f"{older}: from this call on the record is held to {self}"
            else:
                note = (f"{older}: this call collects only, with {self}; the first resume that sends "
                        "holds the record to its rules file")
        elif before.sha256 == self.sha256:
            note = None
        elif new_rules:
            note = f"--new-rules: from this call on the record is held to {self}, not {before}"
        elif sending:
            raise Refused(self._refusal(path, before))
        else:
            note = f"the record is held to {before}; this call collects only, with {self}"
        if note:
            fields["rules_note"] = note
        return fields, note

    def _refusal(self, path, before: "RulesFile") -> str:
        """Why a resume sends nothing with this file, and the ways on: first, the rules it is held to."""
        held = before.path
        if held is None:
            way = "Leave out --rules to send with the rules the record is held to"
        elif held == self.path:
            way = (f"{held} has changed since the record was held to it: put back the file with SHA-256 "
                   f"{before.sha256} to send with those rules")
        else:
            way = f"Give --rules {quoted(held)} to send with the rules the record is held to"
        return (f"{path} sends nothing with this rules file: the record is held to {before}, and this call "
                f"gives {self}. {way}; give --new-rules to change the rules from here on (the resume "
                "line then holds both), or --resume without --max-order to collect only")
