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


def _patterns(text: str) -> str:
    text = JWT.sub(HIDDEN, text)
    for name in SITES:                # then the patterns of each site, in registry order
        for pattern, replacement in SITES[name].profile.secret_patterns:
            text = pattern.sub(replacement, text)
    return text


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


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """The text with every secret and every text in a secret's form taken out."""
    text = _patterns(str(text))
    forms = [form for secret in secrets if secret for form in _forms(str(secret))]
    for form in forms:
        text = _take_out(text, form)
    for form in forms:                # each end only when no form is left whole
        text = _take_ends(text, form)
    return text


def redact_all(value: object, secrets: Sequence[str] = ()) -> object:
    """The same for every text in a value made of dicts, lists and texts. Keys are filtered too."""
    if isinstance(value, str):
        return redact(value, secrets)
    if isinstance(value, dict):
        return {redact_all(k, secrets) if isinstance(k, str) else k: redact_all(v, secrets) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_all(item, secrets) for item in value]
    return value
