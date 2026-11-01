"""The table of the day of VLQ, in an init artefact (wire.TABLE_FILE), and the check of a text against it.

VLQ does not compile or route: register index i is component i of the table, which can change with calibration.
"""

import json
from dataclasses import dataclass
from typing import Final, Self

from ...qasm import Qasm
from ...values import is_int, sha256_hex
from ..pickle_reader import MAX_NODES, PickleRefused, Walk, loads
from ..protocol import TABLE_NOTE

WIDTH = 1024                  # the most entries of one list or dict; the table lists every component
_ONE_QUBIT: Final = ("r", "prx", "measure")
PAIRS: Final = ("cz", "move")
_NOT_CHECKED: Final = ("the text was not checked against the table: the operand reader reads only a text with one "
                       "quantum register, in plain statements")


def _where(gate: str, indices: list[int]) -> str:
    if len(indices) == 1:
        return f"{gate} on index {indices[0]}"
    return f"{gate} on indices {' and '.join(map(str, indices))}" if indices else gate


@dataclass(frozen=True, slots=True, kw_only=True)
class Table:
    """The table of the day: the index of each component, the qubits, the resonators, the loci of cz and move."""

    index: dict[str, int]
    qubits: frozenset[str]
    resonators: frozenset[str]
    loci: dict[str, frozenset[tuple[str, str]]]
    resonator_indices: tuple[int, ...]        # sorted
    fields: dict                              # what the record gets: the size, the resonator indices, the digest

    @classmethod
    def of(cls, *, index: dict[str, int], qubits: frozenset[str], resonators: frozenset[str],
           loci: dict[str, frozenset[tuple[str, str]]]) -> Self:
        """The table of its parts, with the indices of the resonators and the fields of the record."""
        at = tuple(sorted(index[name] for name in resonators))
        # the text of the digest: compact JSON with sorted keys, and each list sorted
        canonical = json.dumps({"index": index, "qubits": sorted(qubits), "resonators": sorted(resonators),
                                "loci": {gate: sorted(map(list, pairs)) for gate, pairs in loci.items()}},
                               sort_keys=True, separators=(",", ":"))
        digest = sha256_hex(canonical.encode("utf-8"))
        return cls(index=index, qubits=qubits, resonators=resonators, loci=loci, resonator_indices=at,
                   fields={"size": len(index), "resonators": list(at), "sha256": digest})

    @classmethod
    def parse(cls, data: bytes) -> Self:
        """The table of the day in an init artefact. PickleRefused for a table that is not read."""
        walk = Walk(list_width=WIDTH, dict_width=WIDTH)
        top = dict(walk.fields(loads(data)))
        index = dict(walk.fields(top.get("iqm_component_to_idx")))
        day = dict(walk.fields(top.get("iqm_dqa")))
        qubits, resonators = walk.entries(day.get("qubits")), walk.entries(day.get("computational_resonators"))
        gates = dict(walk.fields(day.get("gates")))
        loci = {gate: _loci(walk, gates.get(gate)) for gate in PAIRS}
        if walk.cut:
            raise PickleRefused(f"a list or dict in it has more than {WIDTH} entries, or it has more than "
                                f"{MAX_NODES:,} parts")
        wrong = _wrong(index, qubits, resonators, loci)
        if wrong:
            raise PickleRefused(wrong)
        return cls.of(index=index, qubits=frozenset(qubits), resonators=frozenset(resonators),
                      loci={gate: frozenset(p) for gate, p in loci.items()})

    @staticmethod
    def review(data: bytes, text: str) -> tuple[dict, list[str]]:
        """The fields of the init_done line, and the problems of a text against the table of the day."""
        try:
            table = Table.parse(data)
        except PickleRefused as exc:
            unread = f"the table of the day was not read ({exc}), so the text was not checked against it"
            return {TABLE_NOTE: unread}, []
        problems = table.problems(text)
        fields = {"table": table.fields}
        if problems is None:
            return {**fields, TABLE_NOTE: _NOT_CHECKED}, []
        return ({**fields, "table_problems": problems} if problems else fields), problems

    def problems(self, text: str) -> list[str] | None:
        """Each problem of a text against the table, once; None when the operand reader cannot read the text."""
        operations = Qasm.parse(text).operations
        if operations is None:
            return None
        names = {i: name for name, i in self.index.items()}
        found = [self._problem(gate, indices, names) for gate, indices in operations if gate in _ONE_QUBIT + PAIRS]
        return list(dict.fromkeys(p for p in found if p))

    def _problem(self, gate: str, indices: list[int], names: dict) -> str | None:
        where = _where(gate, indices)
        absent = [i for i in indices if i not in names]
        if absent:
            return f"{where}: the table of the day has no index {absent[0]} (its size is {len(self.index)})"
        if gate in _ONE_QUBIT:
            other = [i for i in indices if names[i] not in self.qubits]
            return f"{where}: index {other[0]} is not a qubit in the table of the day" if other else None
        if len(indices) != 2 or names[indices[1]] not in self.resonators:
            at = " or ".join(map(str, self.resonator_indices))
            return f"{where}: the second index is not the resonator, which the table of the day has at {at}"
        if (names[indices[0]], names[indices[1]]) not in self.loci[gate]:
            return f"{where}: the table of the day lists no {gate} locus for these indices"
        return None


def _loci(walk: Walk, info: object) -> list[tuple]:
    """The loci of one gate, in every implementation of it."""
    implementations = dict(walk.fields(info)).get("implementations")
    return [tuple(walk.entries(locus)) for _, one in walk.fields(implementations)
            for locus in walk.entries(dict(walk.fields(one)).get("loci"))]


def _wrong(index: dict, qubits: list, resonators: list, loci: dict) -> str | None:
    """Why a table is not in the form that is read, or None."""
    if not index or not all(isinstance(key, str) and is_int(value) and value >= 0 for key, value in index.items()):
        return "its index table is not a map of names to indices"
    if len(set(index.values())) != len(index):
        return "two components of its index table have one index"
    if not qubits or not all(isinstance(name, str) for name in qubits):
        return "it lists no qubits by name"
    if not resonators or not all(isinstance(name, str) and name in index for name in resonators):
        return "it lists no resonator with an index"
    for gate, pairs in loci.items():
        if not pairs or not all(len(pair) == 2 and all(isinstance(name, str) for name in pair) for pair in pairs):
            return f"it lists no loci of {gate} as pairs of names"
    return None
