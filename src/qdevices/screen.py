"""Output to the screen, which never ends a live call: the record is the truth."""

import os
import shlex
import sys
from contextlib import suppress
from os import PathLike
from typing import TextIO

from .errors import described


def say(text: str = "") -> None:
    """Print a line. A closed pipe or terminal is passed over."""
    with suppress(OSError, ValueError):
        print(text, file=sys.stdout, flush=True)


def warn(text: str) -> None:
    """Print a line on stderr. A closed pipe or terminal is passed over."""
    with suppress(OSError, ValueError):
        print(text, file=sys.stderr, flush=True)


def finish() -> None:
    """The end of a command: what is left on the screen is written out, or else put on the null device.

    A closed pipe is passed over with no word; any other error, such as a full disk, first gets one line on stderr.
    On the null device the exit code stays that of the command: Python writes what is left as it exits, and where
    that write fails, the exit code becomes 120.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except BrokenPipeError:
            _to_null(stream)
        except OSError as exc:
            warn(f"the screen text could not all be written ({described(exc)})")
            _to_null(stream)
        except (AttributeError, ValueError):      # no stream, or one that is closed: nothing is left to write
            pass


def _to_null(stream: TextIO) -> None:
    """The file of a stream that cannot be written, moved to the null device, and what the stream holds put there."""
    with suppress(OSError, ValueError):       # a stream with no file of its own is left as it is
        fd, null = stream.fileno(), os.open(os.devnull, os.O_WRONLY)
        if null != fd:
            try:
                os.dup2(null, fd)
            finally:
                os.close(null)
        stream.flush()


def quoted(path: str | PathLike[str]) -> str:
    """A path in a printed command, quoted for the shell: with a space or a shell character, it stays one word."""
    return shlex.quote(str(path))
