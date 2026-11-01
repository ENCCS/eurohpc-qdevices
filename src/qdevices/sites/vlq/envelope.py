"""The envelope the VLQ service needs around the token, inside each job folder.

The scheme is the service's, not this app's: the site can open the envelope and read the token.
"""

import base64
import hashlib
import secrets
import string
from dataclasses import dataclass, field
from typing import Final, Self

from cryptography.fernet import Fernet

_ALPHABET: Final = string.ascii_letters + string.digits


@dataclass(frozen=True, slots=True, kw_only=True)
class Envelope:
    """The password of one job, raw and in base64 (its USER_JWT_PWD), with which the token is sealed."""

    password: str = field(repr=False)
    encoded: str = field(repr=False)

    @classmethod
    def new(cls, length: int = 50) -> Self:
        """A new password of letters and digits, with its base64 form."""
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(length))
        return cls(password=raw, encoded=base64.b64encode(raw.encode()).decode())

    def seal(self, token: str) -> bytes:
        """The content of the token file of the job: base64 of the Fernet text of the token, keyed by the password."""
        key = base64.urlsafe_b64encode(hashlib.sha256(self.password.encode()).digest())
        return base64.b64encode(Fernet(key).encrypt(token.encode()))
