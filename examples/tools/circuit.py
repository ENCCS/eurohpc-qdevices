"""A circuit on a state vector: its final state, the share of each key, and counts with a simple model of noise."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from gates import ONE, TWO, one_qubit, pauli_error
from texts import read_list, read_text


@dataclass(frozen=True)
class Circuit:
    """The gates in order, and the qubit that each character of a key shows."""

    ops: tuple
    bits: tuple

    @classmethod
    def of_text(cls, text: str) -> Circuit:
        """An OpenQASM 2 or 3 text."""
        return cls(*read_text(text))

    @classmethod
    def of_list(cls, data: dict) -> Circuit:
        """The broker's list of operations."""
        return cls(*read_list(data))

    @property
    def two_qubit(self) -> int:
        """The two-qubit gates."""
        return sum(len(op[1]) == 2 for op in self.ops)

    @property
    def qubits(self) -> tuple:
        """The qubits that a gate touches or a measurement reads, in order; an idle qubit is not one of them."""
        return tuple(sorted({q for _, on, _ in self.ops for q in on} | set(self.bits)))

    def renumbered(self) -> Circuit:
        """The same circuit on the qubits 0 to n - 1, in the order of `qubits`, with no idle qubit."""
        place = {q: n for n, q in enumerate(self.qubits)}
        return Circuit(tuple((name, tuple(place[q] for q in on), args) for name, on, args in self.ops),
                       tuple(place[q] for q in self.bits))

    @property
    def size(self) -> str:
        """Its size, as a line."""
        return f"qubits read {len(self.bits)}, gates {len(self.ops)}, two-qubit gates {self.two_qubit}"

    def final(self, noise: float = 0.0, rng: random.Random | None = None) -> dict:
        """The amplitude of each basis state after all the gates; with noise, one random run."""
        state = {0: 1 + 0j}
        for name, qubits, args in self.ops:
            if len(qubits) == 1:
                state = one_qubit(state, ONE[name](*args), 1 << qubits[0])
            else:
                a, b = 1 << qubits[0], 1 << qubits[1]
                state = TWO[name](state, a, b, *args)
                if noise and rng.random() < noise:
                    state = pauli_error(state, a, b, rng)
        return state

    def key(self, index: int) -> str:
        """The key of a basis state."""
        return "".join("1" if index >> q & 1 else "0" for q in self.bits)

    def shares(self) -> dict:
        """The share of each key on a perfect machine."""
        out = defaultdict(float)
        for i, v in self.final().items():
            out[self.key(i)] += abs(v) ** 2
        return {key: value for key, value in out.items() if value > 1e-9}

    def sample(self, shots: int, noise: float = 0.0, readout: float = 0.0, seed: int = 1) -> dict:
        """Counts of a run with noise: a Pauli error after a two-qubit gate with chance `noise`, then readout flips."""
        rng, counts = random.Random(seed), defaultdict(int)
        runs = min(shots, 1000) if noise else 1
        for run in range(runs):
            state = self.final(noise, rng)
            weights = [abs(v) ** 2 for v in state.values()]
            for index in rng.choices(list(state), weights, k=shots // runs + (run < shots % runs)):
                flips = sum(1 << q for q in self.bits if rng.random() < readout)
                counts[self.key(index ^ flips)] += 1
        return dict(counts)


def circuit_of(file: Path) -> Circuit:
    """The circuit in a file of an example."""
    text = file.read_text(encoding="utf-8")
    return Circuit.of_list(json.loads(text)) if file.suffix == ".json" else Circuit.of_text(text)


def shares_of(text: str) -> dict:
    """The share of each key of a text, to six places."""
    return {key: round(value, 6) for key, value in Circuit.of_text(text).shares().items()}


def amplitudes_of(text: str) -> dict:
    """The amplitude of each key of a text in which every qubit is measured."""
    circuit = Circuit.of_text(text)
    return {circuit.key(i): v for i, v in circuit.final().items()}
