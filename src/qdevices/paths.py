"""The fixed folders of the app; no flag or environment variable, not even HOME, moves them."""

import os
import pwd
from dataclasses import dataclass
from pathlib import Path
from typing import Self


@dataclass(frozen=True, slots=True, kw_only=True)
class Places:
    """The folders of the app and its config file."""

    records: Path     # records/<site>/<run>/run_<UTC>.jsonl, and records/<site>/older_decisions.jsonl
    reads: Path       # reads/<site>/read_<UTC>.json and list_<UTC>.json, made by `check --live`
    state: Path       # <site>.lock, <site>.holder, unlock.jsonl
    config: Path      # qdevices.toml

    @classmethod
    def default(cls) -> Self:
        """The places of the app in the home folder that the user database gives."""
        base = Path(pwd.getpwuid(os.getuid()).pw_dir)
        return cls(records=base / ".local/share/qdevices/records",
                   reads=base / ".local/share/qdevices/reads",
                   state=base / ".local/state/qdevices",
                   config=base / ".config/qdevices/qdevices.toml")
