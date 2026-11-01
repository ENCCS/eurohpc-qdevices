"""Small pure helpers: the integer and number tests of a value read from JSON or TOML, a digest, the id test."""

import hashlib
from typing import Final, TypeGuard

import httpx


def is_int(value: object) -> TypeGuard[int]:
    """True for an int that is not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def is_number(value: object) -> TypeGuard[int | float]:
    """True for an int or a float that is not a bool. NaN and the infinities are numbers here."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


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


def sha256_hex(data: bytes) -> str:
    """The SHA-256 digest of some bytes, as 64 hexadecimal characters."""
    return hashlib.sha256(data).hexdigest()
