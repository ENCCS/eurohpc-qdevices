"""One statement of an OpenQASM text: its gate, the text after its parameters, and its operands."""

import re
from dataclasses import dataclass
from typing import Final, Self

NESTING: Final = 32                   # the most `if (...)` read around one statement; deeper is not read
ENTRIES: Final = 1_000_000            # the most operations read from one text; a text of more is refused
WORD: Final = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)")
_OPERAND: Final = re.compile(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:\[\s*([0-9]+)\s*\])?\s*")
_DECLARATIONS: Final = frozenset({"OPENQASM", "include", "qreg", "creg", "qubit", "bit", "opaque", "input", "output",
                                  "const", "int", "uint", "float", "angle", "bool"})


class TooManyEntries(Exception):
    """A text with more operations than a check reads."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Statement:
    """The gate of one statement and the text after its parameters; an empty gate for a declaration."""

    gate: str
    rest: str

    @classmethod
    def parse(cls, text: str, depth: int = 0) -> Self | None:
        """The statement of a text with no space at either end, also under `if (...)`; None for one it cannot read."""
        word = WORD.match(text)
        if word is None or depth > NESTING:
            return None
        gate, rest = word.group(1), text[word.end():].strip()
        if gate == "if":                                                  # OpenQASM 2: if (c == 1) x q[0]
            rest = cls._after_parentheses(rest)
            return cls.parse(rest, depth + 1) if rest else None
        if "=" in text and "measure" in text.split("=", 1)[1]:            # OpenQASM 3: c[0] = measure q[0]
            return cls.parse(text.split("=", 1)[1].strip(), depth + 1)
        if gate in _DECLARATIONS:
            return cls(gate="", rest="")
        if rest.startswith("("):                                          # the parameters of a gate
            rest = cls._after_parentheses(rest)
        return None if rest is None else cls(gate=gate, rest=rest)

    @classmethod
    def unguarded(cls, text: str) -> str | None:
        """The text under its `if (...)` guards, at most NESTING of them; None when there are more."""
        for _ in range(NESTING + 1):
            word = WORD.match(text)
            if word is None or word.group(1) != "if":
                return text
            text = cls._after_parentheses(text[word.end():].strip()) or ""      # one that does not close: nothing
        return None

    @property
    def operands(self) -> list[re.Match[str]] | None:
        """The operands before any `->`, each a register name and an index or None; None when one cannot be read."""
        found = [_OPERAND.fullmatch(part) for part in self.rest.split("->")[0].split(",")] if self.rest else []
        return None if None in found else found

    def entries(self, name: str, size: int, room: int = ENTRIES) -> list[tuple[str, list[int]]] | None:
        """The operations of the statement on the one register; None when they cannot be read. Over `room` raises."""
        if not self.gate:                                                 # a declaration
            return []
        operands = self.operands
        if operands is None or any(found.group(1) != name for found in operands):
            return None
        indices = [found.group(2) for found in operands]
        if None in indices and len(indices) != 1:
            return None
        if (1 if None not in indices else size) > room:
            raise TooManyEntries
        if None in indices:
            return [(self.gate, [i]) for i in range(size)]
        return [(self.gate, [int(i) for i in indices])]

    @staticmethod
    def _after_parentheses(text: str) -> str | None:
        """The text after a group in parentheses at its start; None when there is none or it does not close."""
        depth = 0
        for index, char in enumerate(text if text.startswith("(") else ""):
            depth += 1 if char == "(" else -1 if char == ")" else 0
            if depth == 0:
                return text[index + 1:].strip()
        return None
