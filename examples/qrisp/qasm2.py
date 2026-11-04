"""Write a compiled Qrisp circuit as an OpenQASM 2 text, from Qrisp's own circuit data.

It changes no gate and chooses no layout: the site compiles the text. It writes only the gates of the original
`qelib1.inc` and refuses any other by name, so break a circuit down first with Qrisp's `qc.transpile()`, and write
`r`, which it keeps, as `rz`, `rx` and `rz`.
"""

from dataclasses import dataclass
from math import pi
from types import MappingProxyType
from typing import Final

__all__ = ["ExportError", "to_qasm2"]

HEADER: Final = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'


@dataclass(frozen=True, slots=True)
class Gate:
    """How one Qrisp operation is written: its OpenQASM 2 name, its number of angles and any fixed angle.

    Qrisp's id holds three angles of zero, and the id of qelib1.inc takes none: `with_angles=False` leaves them out.
    """

    name: str
    angles: int = 0
    fixed: tuple[float, ...] = ()
    with_angles: bool = True


# Qrisp name -> OpenQASM 2, each a gate of the original qelib1.inc; `p` as `rz` and `sx` as `rx(pi/2)` differ by a
# global phase only.
GATES: Final = MappingProxyType({
    "x": Gate("x"), "y": Gate("y"), "z": Gate("z"), "id": Gate("id", 3, with_angles=False), "h": Gate("h"),
    "s": Gate("s"), "s_dg": Gate("sdg"), "t": Gate("t"), "t_dg": Gate("tdg"),
    "rx": Gate("rx", 1), "ry": Gate("ry", 1), "rz": Gate("rz", 1), "p": Gate("rz", 1),
    "u3": Gate("u3", 3), "cx": Gate("cx"), "cy": Gate("cy"), "cz": Gate("cz"),
    "sx": Gate("rx", fixed=(pi / 2,)), "sx_dg": Gate("rx", fixed=(-pi / 2,)),
})
# Bookkeeping of Qrisp, and a global phase: no count shows them.
LEFT_OUT: Final = frozenset({"qb_alloc", "qb_dealloc", "gphase"})
STATEMENTS: Final = frozenset({"measure", "barrier", "reset"})


class ExportError(ValueError):
    """The circuit has an instruction this writer does not write. Nothing is written."""


def _angle(value) -> str:
    try:
        text = repr(float(value))
        return text.replace("e", ".0e") if "e" in text and "." not in text else text  # 1e-05 is not OpenQASM 2
    except (TypeError, ValueError):
        raise ExportError(f"the angle {value!r} is not a number; bind every parameter first") from None


def _line(instr, qubit: dict, clbit: dict) -> str | None:
    name, qs = instr.op.name, [f"q[{qubit[b.identifier]}]" for b in instr.qubits]
    if name in LEFT_OUT:
        return None
    if name == "measure":
        return f"measure {qs[0]} -> c[{clbit[instr.clbits[0].identifier]}];"
    if name in STATEMENTS:
        return f"{name} {','.join(qs)};"
    gate = GATES.get(name)
    if gate is None:
        raise ExportError(f"the gate {name!r} is not written by this writer; break the circuit down with "
                          "qc.transpile() first, and write r, which it keeps, as rz, rx and rz "
                          f"(written: {', '.join(sorted(GATES))})")
    params = list(instr.op.params)
    if len(params) != gate.angles:
        raise ExportError(f"the gate {name!r} has {len(params)} angles, {gate.angles} expected")
    params = [*gate.fixed, *(params if gate.with_angles else [])]
    angles = f"({','.join(_angle(p) for p in params)})" if params else ""
    return f"{gate.name}{angles} {','.join(qs)};"


def to_qasm2(qc) -> str:
    """The OpenQASM 2 text of a compiled, broken-down Qrisp circuit."""
    qubit = {b.identifier: i for i, b in enumerate(qc.qubits)}
    clbit = {b.identifier: i for i, b in enumerate(qc.clbits)}
    lines = [f"qreg q[{len(qubit)}];"] + ([f"creg c[{len(clbit)}];"] if clbit else [])
    for instr in qc.data:
        line = _line(instr, qubit, clbit)
        if line is not None:
            lines.append(line)
    return HEADER + "\n".join(lines) + "\n"
