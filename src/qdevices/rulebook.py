"""The rules file of a user: its hooks, and its path and SHA-256 (content/rules.md)."""

import hashlib
import types
from pathlib import Path

from .errors import Refused
from .rules import Point


class RuleFileError(Refused):
    """The rules file cannot be loaded."""


def load(path: Path | None) -> tuple[dict, dict | None]:
    """The hooks of a user's rules file, and its path and SHA-256 for the start and resume lines."""
    # Called only after the token variable is deleted. The bytes hashed are the bytes run; imports are not hashed.
    if path is None:
        return {}, None
    path = Path(path)
    if not path.is_file():
        raise RuleFileError(f"no rules file at {path}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RuleFileError(f"the rules file {path} cannot be read: {type(exc).__name__}") from None
    module = types.ModuleType("qdevices_user_rules")
    module.__file__ = str(path.absolute())
    try:
        exec(compile(data, str(path), "exec", dont_inherit=True), module.__dict__)
    except (Exception, SystemExit, GeneratorExit) as exc:          # an interrupt stays an interrupt
        raise RuleFileError(f"the rules file {path} cannot be loaded: {type(exc).__name__}: {exc}") from None
    hooks = {point.value: getattr(module, point.value) for point in Point
             if callable(getattr(module, point.value, None))}
    return hooks, {"path": str(path.resolve()), "sha256": hashlib.sha256(data).hexdigest()}
