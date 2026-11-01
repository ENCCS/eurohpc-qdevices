"""What the app reads of the PCSS broker: the code of an expired job, and the operation list of a job file."""

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from ...values import is_int, is_number

EXPIRED_CODE: Final = 4               # with this message, the broker does not know the job
EXPIRED_MESSAGE: Final = "Unknown job. May be expired."


def _qubit(value: object, n: int) -> bool:
    return is_int(value) and 0 <= value < n


def _pair(value: object, n: int) -> bool:
    return (isinstance(value, list) and len(value) == 2 and all(_qubit(q, n) for q in value)
            and value[0] != value[1])


def _angle(value: object, low: float, high: float) -> bool:
    return is_number(value) and low <= value <= high


@dataclass(frozen=True, slots=True)
class _Operation:
    """One kind of operation of the broker: the test of its fields, and the problem when they fail it."""

    needs: str = ""                                               # the problem, after "operation i: "
    fits: Callable[[dict, int], bool] = lambda op, n: True        # its fields, on a circuit of n qubits


_OPERATIONS: Final = MappingProxyType({
    "R": _Operation("R needs a qubit, theta in [0, 1] and phi in [0, 2]",
                    lambda op, n: _qubit(op.get("qubit"), n) and _angle(op.get("theta"), 0.0, 1.0)
                    and _angle(op.get("phi"), 0.0, 2.0)),
    "RZ": _Operation("RZ needs a qubit and phi",                   # Infinity passes here; `unsendable` finds it
                     lambda op, n: _qubit(op.get("qubit"), n) and _angle(op.get("phi"), -math.inf, math.inf)),
    "RXX": _Operation("RXX needs two different qubits and theta in [0, 0.5]",
                      lambda op, n: _pair(op.get("qubits"), n) and _angle(op.get("theta"), 0.0, 0.5)),
    "MEASURE": _Operation(),                                       # no field; its place is checked apart
})


def payload_of(data: bytes) -> dict:
    """The operation list of a job file as parsed, sent as it is; any other content raises ValueError."""
    try:
        payload = json.loads(data)
    except RecursionError:
        raise ValueError("it is nested too deep") from None
    if not isinstance(payload, dict) or set(payload) != {"number_of_qubits", "quantum_circuit"}:
        raise ValueError('the file must be {"number_of_qubits": n, "quantum_circuit": [...]}')
    return payload


def circuit_problems(payload: dict, *, machine_qubits: int, max_ops: int) -> list[str]:
    """The problems of an operation list against the broker's schema and a machine's limits, in the order found."""
    n, ops = payload.get("number_of_qubits"), payload.get("quantum_circuit")
    if not is_int(n) or not 1 <= n <= machine_qubits:
        return [f"number_of_qubits must be 1 to {machine_qubits}"]
    if not isinstance(ops, list) or not ops or len(ops) > max_ops:
        return [f"quantum_circuit must be a list of 1 to {max_ops} operations"]
    kinds = [op.get("operation") if isinstance(op, dict) else None for op in ops]
    problems: list[str] = []
    if kinds.count("MEASURE") != 1 or kinds[-1] != "MEASURE":
        problems.append("there must be exactly one MEASURE, as the last operation")
    for i, (op, kind) in enumerate(zip(ops, kinds, strict=True)):
        row = _OPERATIONS.get(kind) if isinstance(kind, str) else None       # a list or a dict is no kind
        if row is None:
            problems.append(f"operation {i}: unknown operation {kind!r}")
        elif not row.fits(op, n):
            problems.append(f"operation {i}: {row.needs}")
    return problems


def unsendable(payload: dict) -> list[str]:
    """The problem of an operation list that the JSON of a request cannot carry, encoded as httpx encodes it."""
    try:
        json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
    except UnicodeEncodeError:
        return ["the file holds a lone surrogate escape, which a JSON request cannot carry"]
    except ValueError:
        return ["the file holds NaN or Infinity, which a JSON request cannot carry"]
    return []
