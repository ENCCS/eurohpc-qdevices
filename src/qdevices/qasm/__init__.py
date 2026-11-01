"""A light reading of an OpenQASM 2 or 3 text for the checks; not a parser, and it changes nothing."""

import re
from dataclasses import dataclass, field
from typing import Final, Self

from .statement import ENTRIES, WORD, Statement, TooManyEntries

__all__ = ["DEPTH", "DIGITS", "Qasm"]

DEPTH: Final = 32                     # how deep calls of defined gates are followed
DIGITS: Final = 5                     # a register or index of more digits is refused unread: no machine is near it
_BRACKETED: Final = re.compile(r"\[\s*([0-9]+)\s*\]")
_COMMENT: Final = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_GATE_DEF: Final = re.compile(r"\bgate\s+([A-Za-z_][A-Za-z0-9_]*)[^{]*\{([^}]*)\}")     # the name and the body
_QREG: Final = re.compile(r"\bqreg\s+[A-Za-z_][A-Za-z0-9_]*\s*\[\s*([0-9]+)\s*\]")
_QUBIT: Final = re.compile(r"\bqubit\s*\[\s*([0-9]+)\s*\]")
_REGISTER: Final = re.compile(r"\bqreg\s+([A-Za-z_][A-Za-z0-9_]*)\s*\[\s*([0-9]+)\s*\]|"
                              r"\bqubit\s*\[\s*([0-9]+)\s*\]\s*([A-Za-z_][A-Za-z0-9_]*)")
_UNSIZED: Final = re.compile(r"\bqubit\s+([A-Za-z_][A-Za-z0-9_]*)")      # `qubit a;`: a name declared with no size
_NOT_GATES: Final = frozenset({"OPENQASM", "include", "qreg", "creg", "qubit", "bit", "opaque", "reset", "if", "input",
                               "output"})


@dataclass(frozen=True, slots=True, kw_only=True)
class Qasm:
    """An OpenQASM text with its comments taken out (clean) and then its gate definitions too (body)."""

    clean: str
    body: str

    @classmethod
    def parse(cls, text: str) -> Self:
        """A text read once: its comments taken out, then its gate definitions."""
        clean = _COMMENT.sub("", text)
        return cls(clean=clean, body=_GATE_DEF.sub("", clean))

    @property
    def declared_gates(self) -> set[str]:
        """The names of the gates the text defines."""
        return {name for name, _ in _GATE_DEF.findall(self.clean)}

    @property
    def too_large(self) -> bool:
        """Whether a number in brackets, a register size or an index, has more than DIGITS; then it is not read."""
        return any(len(digits) > DIGITS for digits in _BRACKETED.findall(self.clean))

    @property
    def qubits(self) -> int:
        """The number of qubits the text declares: the sum of its quantum registers."""
        return sum(int(n) for n in _QREG.findall(self.clean)) + sum(int(n) for n in _QUBIT.findall(self.clean))

    @property
    def gate_names(self) -> set[str]:
        """The names of the operations the text applies, measure and barrier among them."""
        names = set()
        for statement in self.body.split(";"):
            statement = Statement.unguarded(statement.strip())      # a gate under `if (c)` is a gate too
            if not statement:
                continue
            if "=" in statement and "measure" in statement:      # OpenQASM 3: c[0] = measure q[0]
                names.add("measure")
                continue
            found = WORD.match(statement)
            if found and found.group(1) not in _NOT_GATES:
                names.add(found.group(1))
        return names

    @property
    def register(self) -> tuple[str, int] | None:
        """The name and size of the one quantum register of the text; None for a text with none or several."""
        found = _REGISTER.findall(self.body)
        if len(found) != 1:
            return None
        qreg, qreg_size, qubit_size, qubit = found[0]
        return (qreg, int(qreg_size)) if qreg else (qubit, int(qubit_size))

    @property
    def operations(self) -> list[tuple[str, list[int]]] | None:
        """The operations of a one-register text, in order, as (name, qubit indices); None for one it cannot read."""
        try:
            return self._expanded()
        except TooManyEntries:
            return None

    @property
    def too_many(self) -> bool:
        """True for a text with more operations than the checks read: it is refused, as it would go unchecked."""
        try:
            self._expanded()
        except TooManyEntries:
            return True
        return False

    def _expanded(self) -> list[tuple[str, list[int]]] | None:
        register = None if self.too_large else self.register
        if register is None or "{" in self.body:
            return None
        out = []
        for text in filter(None, (part.strip() for part in self.body.split(";"))):
            statement = Statement.parse(text)
            entries = None if statement is None else statement.entries(*register, ENTRIES - len(out))
            if entries is None:
                return None
            out += entries
        return out

    @property
    def gate_count(self) -> int | None:
        """The gate operations, as a limit of shots times gates counts them; None for a text it cannot read."""
        if "{" in self.body or self.too_large:
            return None
        sizes = dict.fromkeys(_UNSIZED.findall(self.body), 1)
        sizes |= {qreg or qubit: int(qreg_size or qubit_size)
                  for qreg, qreg_size, qubit_size, qubit in _REGISTER.findall(self.body)}
        return _GateCount(bodies=dict(_GATE_DEF.findall(self.clean)), sizes=sizes).total(self.body, 0)

    def qubit_problems(self, read: dict | None) -> list[str]:
        """The qubits the text declares against the qubits of a saved read, where the read has them."""
        if self.too_large:
            return [f"the file names a register or an index of more than {DIGITS} digits, more than any machine has"]
        if self.too_many:
            return [f"the text has more than {ENTRIES:,} operations, more than the checks read"]
        if read and isinstance(read.get("qubits"), int) and (declared := self.qubits) > read["qubits"]:
            return [f"the text declares {declared} qubits, the machine has {read['qubits']}"]
        return []


@dataclass(slots=True, kw_only=True)
class _GateCount:
    """The count of one text: the bodies of the gates it defines and the size of each quantum register."""

    bodies: dict[str, str]                                      # gate name -> its body text
    sizes: dict[str, int]                                       # register name -> its qubit count
    done: dict[str, int | None] = field(default_factory=dict)   # gate name -> the count of its body, once counted

    def total(self, statements: str, depth: int) -> int | None:
        """The sum over the statements of the text (depth 0) or of the body of a defined gate (depth 1 on)."""
        counts = [self.statement(part.strip(), depth) for part in statements.split(";") if part.strip()]
        return None if None in counts else sum(counts)

    def statement(self, text: str, depth: int) -> int | None:
        """The operations of one statement; None when it cannot be read."""
        found = Statement.parse(text)
        if found is None or found.gate in ("", "barrier"):
            return None if found is None else 0
        times = self.times(found, depth)
        if times is None or found.gate not in self.bodies:
            return times
        inner = self.body(found.gate, depth)
        return None if inner is None else times * inner

    def times(self, statement: Statement, depth: int) -> int | None:
        """How often a statement applies: once, or at the top once for each qubit of a whole register."""
        operands = statement.operands
        if operands is None or depth:                 # in the body of a gate each operand is one qubit
            return None if operands is None else 1
        whole = [self.sizes.get(found.group(1)) for found in operands if found.group(2) is None]
        return None if None in whole else max(whole, default=1)    # None: a register whose size is not a number

    def body(self, gate: str, depth: int) -> int | None:
        """The operations of the body of a gate the text defines, counted once; None deeper than DEPTH."""
        if gate not in self.done:
            self.done[gate] = None if depth >= DEPTH else self.total(self.bodies[gate], depth + 1)
        return self.done[gate]
