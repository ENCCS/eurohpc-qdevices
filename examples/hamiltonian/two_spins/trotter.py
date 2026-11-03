"""The two spins as a text: N first-order Trotter steps in OpenQASM 2, in Python's standard library alone.

It writes the gates in the order Qrisp's `trotterization` writes them, so a text for the field 1.2 and 5 steps gives
the same shares as STEPS5.qasm. The jobs of this folder are written by Qrisp: see write_two_spins.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import pi

COUPLING = 1.0                       # J of H = -J Z0 Z1 - h (X0 + X1)
FIELD = 1.2                          # h, the transverse field
T = 2 * pi / 2.6                     # the time of the jobs: 2.6 = sqrt(J^2 + 4 h^2), one of the levels
HEADER = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\n'
MEASURE = "measure q[0] -> c[0];\nmeasure q[1] -> c[1];\n"


@dataclass(frozen=True)
class Steps:
    """N first-order Trotter steps of H = -J Z0 Z1 - h (X0 + X1) from 00 to the time t: the ZZ term, then X."""

    steps: int = 5
    field: float = FIELD
    t: float = T
    coupling: float = COUPLING

    def one_step(self) -> str:
        """One step: CX, RZ, CX turns ZZ; H, RZ, H turns X on each spin. RZ(a) is exp(-i a Z / 2)."""
        dt = self.t / self.steps
        zz, x = repr(-2 * self.coupling * dt), repr(-2 * self.field * dt)
        return (f"cx q[0],q[1];\nrz({zz}) q[1];\ncx q[0],q[1];\nh q[1];\nh q[0];\nrz({x}) q[1];\nrz({x}) q[0];\n"
                "h q[1];\nh q[0];\n")

    def text(self) -> str:
        """The whole text: the steps, then both qubits measured; a key reads q[1] q[0]."""
        return HEADER + self.one_step() * self.steps + MEASURE
