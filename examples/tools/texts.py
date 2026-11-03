"""Read a circuit: an OpenQASM 2 or 3 text, or the broker's list of operations. Python's standard library alone."""

from __future__ import annotations

import ast
import operator
import re
from math import pi

from gates import ONE, TWO

SKIP = ("OPENQASM", "include", "qreg", "creg", "qubit", "bit", "barrier")
COMMENT = re.compile(r"//[^\n]*")
GATE_BODY = re.compile(r"\bgate\b[^{]*\{[^}]*\}")
REGISTER = re.compile(r"\bqreg\s+\w+|\bqubit\[\d+\]\s+\w+")
MEASURE = (re.compile(r"measure\s+\w+\[(?P<q>\d+)\]\s*->\s*\w+\[(?P<c>\d+)\]"),
           re.compile(r"\w+\[(?P<c>\d+)\]\s*=\s*measure\s+\w+\[(?P<q>\d+)\]"))
GATE = re.compile(r"(\w+)(?:\(([^)]*)\))?\s+(.+)")
BROKER = {"R": lambda op: ("r", (op["qubit"],), (op["theta"] * pi, op["phi"] * pi)),
          "RZ": lambda op: ("rz", (op["qubit"],), (op["phi"] * pi,)),
          "RXX": lambda op: ("rxx", tuple(op["qubits"]), (op["theta"] * pi,))}
BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def angle(text: str) -> float:
    """A number, or a sum of numbers and pi, as the texts write their angles."""
    def value(node: ast.AST) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name) and node.id == "pi":
            return pi
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -value(node.operand)
        if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
            return BINARY[type(node.op)](value(node.left), value(node.right))
        raise ValueError(f"not an angle: {text}")
    return value(ast.parse(text.strip(), mode="eval").body)


def _gate(line: str) -> tuple:
    found = GATE.fullmatch(line)
    name, args, where = found.groups() if found else (line, "", "")
    qubits = tuple(int(q) for q in re.findall(r"\[(\d+)\]", where))
    if len(qubits) not in (1, 2) or name not in (ONE if len(qubits) == 1 else TWO):
        raise ValueError(f"this emulator does not take: {line}")
    return name, qubits, tuple(angle(a) for a in args.split(",")) if args else ()


def read_text(text: str) -> tuple:
    """The gates of a text, and the qubit each character of a key shows: the highest classical bit first."""
    text = GATE_BODY.sub("", COMMENT.sub("", text))
    if len(REGISTER.findall(text)) > 1:
        raise ValueError("this emulator takes one quantum register")
    ops, measured = [], {}
    for line in (s.strip() for s in text.split(";")):
        found = next((m for m in (p.search(line) for p in MEASURE) if m), None)
        if found:
            measured[int(found["c"])] = int(found["q"])
        elif line and not line.startswith(SKIP):
            ops.append(_gate(line))
    return tuple(ops), tuple(measured[c] for c in sorted(measured, reverse=True))


def read_list(data: dict) -> tuple:
    """The gates of the broker's list, with its angles in units of pi, and its keys, which read qubit 0 first."""
    wrong = {op["operation"] for op in data["quantum_circuit"]} - set(BROKER) - {"MEASURE"}
    if wrong:
        raise ValueError(f"not an operation of the broker: {sorted(wrong)}")
    ops = tuple(BROKER[op["operation"]](op) for op in data["quantum_circuit"] if op["operation"] in BROKER)
    return ops, tuple(range(data["number_of_qubits"]))
