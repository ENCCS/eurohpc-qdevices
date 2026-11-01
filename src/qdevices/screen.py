"""Output to the screen, which never ends a live call: the record is the truth."""

import shlex
import sys
from contextlib import suppress
from os import PathLike


def say(text: str = "") -> None:
    """Print a line. A closed pipe or terminal is passed over."""
    with suppress(OSError, ValueError):
        print(text, file=sys.stdout, flush=True)


def warn(text: str) -> None:
    """Print a line on stderr. A closed pipe or terminal is passed over."""
    with suppress(OSError, ValueError):
        print(text, file=sys.stderr, flush=True)


def quoted(path: str | PathLike[str]) -> str:
    """A path in a printed command, quoted for the shell: with a space or a shell character, it stays one word."""
    return shlex.quote(str(path))
