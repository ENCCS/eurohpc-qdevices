"""The same two spins in Qrisp: the function that writes the jobs, the text it gives, and Qrisp's own emulator.

It needs Qrisp, and examples/qrisp on the path, where programs.py holds the function `ising2`.
"""

from __future__ import annotations

import hashlib
import inspect
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from programs import Program, ising2
from qasm2 import to_qasm2


def source() -> str:
    """The code of `ising2`: the Hamiltonian as Qrisp operators, and its trotterization."""
    return inspect.getsource(ising2)


def text(steps: int) -> str:
    """The OpenQASM 2 text of N steps, by Qrisp's compile and the writer of the Qrisp examples."""
    return to_qasm2(Program(f"STEPS{steps}", "", "", lambda: ising2(steps=steps)).circuit())


def sha256(text: str) -> str:
    """The SHA-256 of a text, as the manifest holds it."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def emulated(steps: int) -> dict:
    """The share of each label on Qrisp's own emulator, with no noise; a Qrisp label reads q[0] first."""
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return {label: round(float(share), 6) for label, share in ising2(steps=steps).get_measurement().items()}
