"""The token filter, applied to every record line, error, downloaded log and traceback.

The patterns need no state, so a log of an earlier process is filtered alike. Each start and each end of 8
characters or more of a secret is taken out too: a body or a log is cut, and a cut can fall inside a secret.
"""

import json
import re
from collections.abc import Iterable, Sequence
from typing import Final

from .sites import SITES
from .sites.facts import HIDDEN

# Any JWT, so a refreshed token, or one held by a service, is taken out too.
JWT: Final = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]+)?")
_SHORTEST: Final = 8                   # the shortest start of a secret taken out


def _forms(secret: str) -> list[str]:
    return list(dict.fromkeys((secret, json.dumps(secret)[1:-1])))       # in this order: no hash order


def _take_out(text: str, form: str) -> str:
    if len(form) < _SHORTEST:
        return text.replace(form, HIDDEN)
    for k in range(len(form), _SHORTEST - 1, -1):      # the whole secret first, then each shorter start
        if form[:_SHORTEST] not in text:
            break
        text = text.replace(form[:k], HIDDEN)
    return text


def _take_ends(text: str, form: str) -> str:
    for k in range(len(form) - 1, _SHORTEST - 1, -1):
        if form[-_SHORTEST:] not in text:
            break
        text = text.replace(form[-k:], HIDDEN)
    return text


class Mask:
    """The token filter of some secrets, made once for a value: the patterns, then each form of each secret."""

    def __init__(self, secrets: Iterable[str] = ()) -> None:
        self.patterns = [(JWT, HIDDEN), *(row for name in SITES for row in SITES[name].profile.secret_patterns)]
        self.forms = [form for secret in secrets if secret for form in _forms(str(secret))]

    def text(self, text: str) -> str:
        """The text with every secret and every text in a secret's form taken out."""
        text = str(text)
        for pattern, replacement in self.patterns:      # the JWT, then the patterns of each site, in registry order
            text = pattern.sub(replacement, text)
        for form in self.forms:
            text = _take_out(text, form)
        for form in self.forms:                # each end only when no form is left whole
            text = _take_ends(text, form)
        return text

    def value(self, value: object) -> object:
        """The same for every text in a value made of dicts, lists and texts. Keys are filtered too."""
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {self.value(k) if isinstance(k, str) else k: self.value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [self.value(item) for item in value]
        return value


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """The text with every secret and every text in a secret's form taken out."""
    return Mask(secrets).text(text)


def redact_all(value: object, secrets: Sequence[str] = ()) -> object:
    """The same for every text in a value made of dicts, lists and texts. Keys are filtered too."""
    return Mask(secrets).value(value)
