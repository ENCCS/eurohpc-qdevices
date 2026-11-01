"""The cz loci in a read of Euro-Q-Exa, the layout they give, and the check of the pairs of a text.

With no_modify the site does not map a text, so each two-qubit gate must act on a listed cz pair.
"""

import re
from typing import TYPE_CHECKING, Final

from ..layout import Layout
from ..values import is_int

if TYPE_CHECKING:
    from ..qasm import Qasm

_LOCUS: Final = re.compile(r"\(\s*([0-9]+)\s*,\s*([0-9]+)\s*\)")
_NOT_PAIRS: Final = frozenset({"barrier", "measure", "reset"})
NOT_MADE: Final = "the pair check was not made"


def _table(instructions: object, gate: str) -> object:
    """The table of one gate in the instructions of a read: a list of [name, table], or a map of name to table."""
    if isinstance(instructions, dict):
        return instructions.get(gate)
    for entry in instructions if isinstance(instructions, (list, tuple)) else []:
        if isinstance(entry, (list, tuple)) and len(entry) == 2 and entry[0] == gate:
            return entry[1]
    return None


def _pair(locus: object) -> tuple[int, int] | None:
    if isinstance(locus, str):
        found = _LOCUS.fullmatch(locus.strip())
        try:
            return (int(found.group(1)), int(found.group(2))) if found else None
        except ValueError:                        # more digits than int reads
            return None
    if isinstance(locus, (list, tuple)) and len(locus) == 2 and all(is_int(i) for i in locus):
        return (locus[0], locus[1])
    return None


def _cz_loci(read: object) -> list[tuple[int, int]] | None:
    """The cz loci of a read as (a, b), as listed. None when it lists none, or one cannot be read."""
    table = _table(read.get("instructions"), "cz") if isinstance(read, dict) else None
    loci = [_pair(locus) for locus in table] if isinstance(table, (dict, list)) else []
    return loci if loci and None not in loci else None


def layout_of(read: dict) -> dict:
    """layout_sha256, qubits and pairs of a read (layout.py)."""
    loci, qubits = _cz_loci(read), read.get("qubits")
    if loci is None or not is_int(qubits):
        return {"layout_sha256": None, "qubits": qubits, "pairs": None}
    return Layout.of(qubits, loci).fields


def pair_check(parsed: "Qasm", read: dict) -> tuple[list[str], list[str]]:
    """(problems, notes) of the two-qubit gates of a text against the cz loci of a read."""
    operations = parsed.operations
    if operations is None:
        return [], [f"{NOT_MADE}: it reads only a text with one quantum register, in plain statements"]
    used = {(gate, tuple(qubits)) for gate, qubits in operations if len(qubits) == 2 and gate not in _NOT_PAIRS}
    if not used:
        return [], []
    loci = _cz_loci(read)
    if loci is None:
        return [], [f"{NOT_MADE}: the cz loci of the read cannot be read"]
    listed, problems, notes = set(loci), [], []
    for gate, (a, b) in sorted(used):
        if (a, b) in listed:
            continue
        if (b, a) in listed:
            notes.append(f"{gate} on qubits {a} and {b}: the read lists the pair as ({b}, {a})")
        else:
            problems.append(f"{gate} on qubits {a} and {b}: the read lists no cz locus ({a}, {b}) or ({b}, {a})")
    return problems, notes
