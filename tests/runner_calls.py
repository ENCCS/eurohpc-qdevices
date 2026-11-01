"""The live calls that the record, stop and transcript goldens share, over the fake sites."""

from dataclasses import dataclass, field

import pytest
from fakes import FakeClock, cfg

from qdevices import runner
from qdevices.paths import Places

RULES_A = {"path": "rules_a.py", "sha256": "a" * 64}         # synthetic: the form rulebook.load gives
RULES_B = {"path": "rules_b.py", "sha256": "b" * 64}


def ctrl_c():
    """A FakeSite job state that is Ctrl-C: FakeSite.status calls it."""
    raise KeyboardInterrupt()


@dataclass
class Calls:
    """The live calls of one case: the exit code of each and, with capsys, what each printed (out, err)."""

    places: Places
    clock: FakeClock
    capsys: pytest.CaptureFixture | None = None
    codes: list = field(default_factory=list)
    printed: list = field(default_factory=list)

    def send(self, manifest, site, *, clock: FakeClock | None = None, **kw) -> int:
        """One live call, with the clock of the case or with `clock`, the clock a fake site was made with."""
        when = self.clock if clock is None else clock
        code = runner.send(manifest, site, cfg=cfg(), places=self.places, clock=when, sleep=when.sleep,
                           host="host-a", **kw)
        self.codes.append(code)
        if self.capsys is not None:
            self.printed.append(self.capsys.readouterr())
        return code

    def exits(self) -> str:
        """The exit codes of the calls in turn, as a golden gives them: "exit 2", or "exit 130, then 1"."""
        return "exit " + ", then ".join(map(str, self.codes))
