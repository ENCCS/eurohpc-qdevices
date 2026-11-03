"""The gates of the emulator, on a state held as {basis state: amplitude}. Python's standard library alone."""

from __future__ import annotations

import random
from cmath import exp
from collections import defaultdict
from math import cos, pi, sin, sqrt


def rx(a: float) -> tuple:
    """exp(-i a/2 X)."""
    return (cos(a / 2), -1j * sin(a / 2), -1j * sin(a / 2), cos(a / 2))


def rz(a: float) -> tuple:
    """exp(-i a/2 Z)."""
    return (exp(-0.5j * a), 0, 0, exp(0.5j * a))


def prx(theta: float, phi: float) -> tuple:
    """exp(-i theta/2 (X cos phi + Y sin phi)), the rotation `r` of the machines' own gates."""
    across = sin(theta / 2)
    return (cos(theta / 2), -1j * exp(-1j * phi) * across, -1j * exp(1j * phi) * across, cos(theta / 2))


def ry(a: float) -> tuple:
    """exp(-i a/2 Y)."""
    return (cos(a / 2), -sin(a / 2), sin(a / 2), cos(a / 2))


def u3(theta: float, phi: float, lam: float) -> tuple:
    """The u3 of qelib1.inc."""
    across = sin(theta / 2)
    return (cos(theta / 2), -exp(1j * lam) * across, exp(1j * phi) * across, exp(1j * (phi + lam)) * cos(theta / 2))


ONE = {"x": lambda: (0, 1, 1, 0), "y": lambda: (0, -1j, 1j, 0), "z": lambda: (1, 0, 0, -1),
       "h": lambda: (1 / sqrt(2), 1 / sqrt(2), 1 / sqrt(2), -1 / sqrt(2)),
       "s": lambda: (1, 0, 0, 1j), "sdg": lambda: (1, 0, 0, -1j),
       "t": lambda: (1, 0, 0, exp(0.25j * pi)), "tdg": lambda: (1, 0, 0, exp(-0.25j * pi)),
       "rx": rx, "ry": ry, "rz": rz, "u3": u3, "r": prx}


def _clean(out: dict) -> dict:
    return {i: v for i, v in out.items() if abs(v) > 1e-12}


def one_qubit(state: dict, gate: tuple, bit: int) -> dict:
    """A gate (a, b, c, d) on the qubit of a bit mask."""
    out = defaultdict(complex)
    for i, v in state.items():
        low, high = i & ~bit, i | bit
        out[low] += (gate[1] if i & bit else gate[0]) * v
        out[high] += (gate[3] if i & bit else gate[2]) * v
    return _clean(out)


def _cx(state: dict, a: int, b: int) -> dict:
    return {i ^ b if i & a else i: v for i, v in state.items()}


def _cy(state: dict, a: int, b: int) -> dict:
    return {i ^ b if i & a else i: (-1j if i & b else 1j) * v if i & a else v for i, v in state.items()}


def _cz(state: dict, a: int, b: int) -> dict:
    return {i: -v if i & a and i & b else v for i, v in state.items()}


def _crz(state: dict, a: int, b: int, theta: float) -> dict:
    return {i: v * exp((0.5j if i & b else -0.5j) * theta) if i & a else v for i, v in state.items()}


def _move(state: dict, a: int, b: int) -> dict:
    """A swap: the phases of the real MOVE cancel in a pair, as the texts use it."""
    return {i ^ (a | b) if bool(i & a) != bool(i & b) else i: v for i, v in state.items()}


def _rxx(state: dict, a: int, b: int, theta: float) -> dict:
    out = defaultdict(complex)
    for i, v in state.items():
        out[i] += cos(theta / 2) * v
        out[i ^ (a | b)] += -1j * sin(theta / 2) * v
    return _clean(out)


TWO = {"cx": _cx, "cy": _cy, "cz": _cz, "crz": _crz, "move": _move, "rxx": _rxx}


def pauli_error(state: dict, a: int, b: int, rng: random.Random) -> dict:
    """One of the 15 Pauli errors on two qubits, at random, up to a global phase, which no count shows."""
    flip, sign = 0, 0
    while not (flip or sign):
        flip, sign = rng.choice((0, a)) | rng.choice((0, b)), rng.choice((0, a)) | rng.choice((0, b))
    return {i ^ flip: -v if bin(i & sign).count("1") % 2 else v for i, v in state.items()}
