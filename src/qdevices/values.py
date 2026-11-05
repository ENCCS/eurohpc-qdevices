"""Small helpers of the values the app reads and writes.

The integer and number tests of a value read from JSON or TOML, the seconds of a measure, a value for standard JSON,
the test of a file, a digest and the id test.
"""

import errno
import hashlib
import json
import math
import stat
from pathlib import Path
from typing import Final, TypeGuard

import httpx


def is_int(value: object) -> TypeGuard[int]:
    """True for an int that is not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value: object) -> TypeGuard[int | float]:
    """True for an int or a float that is not a bool. NaN and the infinities are numbers here."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def measure(seconds: float | None) -> float | None:
    """Seconds of 0 or more as they are; None for no seconds, NaN or a time below zero, which is no measure."""
    return seconds if seconds is not None and seconds >= 0 else None


def standard_json(value: object) -> object:
    """A value that standard JSON holds: NaN and the infinities, which it cannot, as texts of the same words."""
    if isinstance(value, float) and not math.isfinite(value):
        return json.dumps(value)                  # "NaN", "Infinity" or "-Infinity", as a bare token would be
    if isinstance(value, dict):
        return {key: standard_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [standard_json(item) for item in value]
    return value


ANSWER_DEPTH: Final = 200             # the deepest answer read: the code after it recurses once a level


def too_deep(value: object, most: int = ANSWER_DEPTH) -> bool:
    """True for a value of dicts and lists nested more than `most` levels; read level by level, with no recursion."""
    level = [value]
    for _ in range(most + 1):
        level = [inner for item in level if isinstance(item, (dict, list, tuple, set))
                 for inner in (item.values() if isinstance(item, dict) else item)]
        if not level:
            return False
    return True


def in_url(job_id: str) -> bool:
    """True for a job id that httpx puts at the end of a URL path as it is, so that it reads that job back."""
    try:
        return httpx.URL(f"https://site/{job_id}").path == f"/{job_id}"
    except (httpx.InvalidURL, UnicodeEncodeError):       # a lone surrogate cannot be encoded
        return False


_NONE_THERE: Final = frozenset({errno.ENOENT, errno.ENOTDIR, errno.EBADF, errno.ELOOP})    # as pathlib of 3.12 has it


def regular_file(path: Path) -> bool:
    """True for a regular file at a path, False for none there; any other error of Path.stat is raised.

    None there, as Path.is_file of Python 3.12 has it: no such path, a part of it that is not a folder, a link loop,
    or a null byte. Path.is_file of Python 3.14 gives False at any error, as in a folder that cannot be searched. A
    folder or a FIFO is no file here, so it is never opened: a FIFO with no writer would block.
    """
    try:
        return stat.S_ISREG(path.stat().st_mode)
    except OSError as exc:
        if exc.errno in _NONE_THERE:
            return False
        raise
    except ValueError:                    # a null byte: no file has that path
        return False


def sha256_hex(data: bytes) -> str:
    """The SHA-256 digest of some bytes, as 64 hexadecimal characters."""
    return hashlib.sha256(data).hexdigest()
