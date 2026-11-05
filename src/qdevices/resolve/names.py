"""The decisions of `qdevices resolve` that set the seconds an order counts: one source of their flags and words."""

from collections.abc import Sequence
from types import MappingProxyType
from typing import Final

DECISIONS: Final = MappingProxyType({"over_limit": "over the limit", "expired": "expired",
                                     "unreadable": "unreadable", "gone": "gone"})   # name, as argparse has it: words


def flag(name: str) -> str:
    """The option of a decision on the command line: --over-limit for over_limit."""
    return "--" + name.replace("_", "-")


def joined(items: Sequence[str], last: str = "or") -> str:
    """The items with commas between them, and `last` before the last one: "a, b or c"."""
    return f"{', '.join(items[:-1])} {last} {items[-1]}" if len(items) > 1 else "".join(items)
