"""SIGTERM and SIGHUP end a live call as Ctrl-C does. Nothing is cancelled by any of them."""

import signal
from typing import Final, Self

KILLS: Final = (signal.SIGTERM, signal.SIGHUP)


def _as_interrupt(signum, frame):
    raise KeyboardInterrupt(signal.Signals(signum).name)


class KillsAsInterrupt:
    """SIGTERM and SIGHUP as an interrupt for the body of a `with`, then each handler as it was."""

    def __init__(self) -> None:
        self.earlier: dict = {}

    def __enter__(self) -> Self:
        """Each signal as an interrupt; a signal set to ignore stays ignored (nohup)."""
        self.earlier = {number: signal.getsignal(number) for number in KILLS}
        for number, handler in self.earlier.items():
            if handler != signal.SIG_IGN:
                signal.signal(number, _as_interrupt)
        return self

    def __exit__(self, *exc: object) -> None:
        """Each handler as it was; an earlier handler of None is set back as the default."""
        for number, handler in self.earlier.items():
            signal.signal(number, handler if handler is not None else signal.SIG_DFL)
