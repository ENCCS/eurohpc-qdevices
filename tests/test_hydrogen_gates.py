"""examples/hamiltonian, the curve of H2: the gates by Qrisp against the closed form and the stored run."""

import sys
from pathlib import Path

import pytest

pytest.importorskip("qrisp")
np = pytest.importorskip("numpy")
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "examples" / path) for path in ("hamiltonian", "tools", "qrisp")]
from circuit import Circuit  # noqa: E402
from hydrogen import Curve, lowest_strong_peak  # noqa: E402
from molecule import Molecule, PhaseEstimation  # noqa: E402
from qasm2 import to_qasm2  # noqa: E402
from qrisp.operators import X, Z  # noqa: E402
from with_qrisp import BITS, LENGTHS, STEPS, curve, h2, operator, phase_register, point, shares_at, size_of  # noqa: E402

SHARES = 1e-3                       # Qrisp's emulator drops shares under 1e-5, scales, rounds and scales again


def in_double_precision(phase) -> dict[float, float]:
    """The share of each phase of a register, from its gates as a text, on the state vector of examples/tools."""
    compiled = phase.qs.compile()
    compiled.measure(list(phase.reg))
    shares = Circuit.of_text(to_qasm2(compiled.transpile())).shares()
    return {int(key, 2) / 2 ** len(phase.reg): share for key, share in shares.items()}


def test_the_hamiltonian_of_the_page_is_built_from_its_terms():
    page = -1.05237325 + 0.39793742 * Z(0) - 0.39793742 * Z(1) - 0.0112801 * Z(0) * Z(1) + 0.1809312 * X(0) * X(1)
    assert np.allclose(h2().to_array(), page.to_array())
    assert np.allclose(operator(Molecule(0.735).terms).to_array(), page.to_array(), atol=1e-7)


def test_the_gates_give_the_closed_form_at_any_length_and_their_number_does_not_depend_on_it():
    for r in (0.7414, 2.6):
        made, closed = shares_at(r, 6), PhaseEstimation(Molecule(r), 6, STEPS).shares()
        assert max(abs(made.get(phase, 0.0) - share) for phase, share in closed.items()) < SHARES
        assert size_of(phase_register(operator(Molecule(r).terms), 6)) == (8, 2307)


@pytest.mark.parametrize(("length", "bits"), [(0.7414, 6), (2.6, 6), (0.5, 8)])
def test_the_gates_on_a_double_precision_state_vector_give_the_closed_form_to_the_last_digits(length, bits):
    made = in_double_precision(phase_register(operator(Molecule(length).terms), bits))
    assert sum(made.values()) == pytest.approx(1.0)
    closed = PhaseEstimation(Molecule(length), bits, STEPS).shares()
    assert max(abs(made.get(phase, 0.0) - share) for phase, share in closed.items()) < 1e-10


def test_qrisp_makes_a_point_of_the_stored_run_again():
    run = Curve.stored()
    made, held = point(2.6, run.bits), run.at(2.6)
    for name in ("length", "nuclear", "exact", "overlap", "phase", "top_phase"):
        assert getattr(made, name) == getattr(held, name)
    assert made.share == pytest.approx(held.share, abs=1e-4)
    assert made.top_share == pytest.approx(held.top_share, abs=1e-4)


def test_a_run_holds_its_bits_steps_and_lengths():
    made = curve((2.6,), 4)
    assert (made.bits, made.steps, made.qubits, made.gates) == (4, STEPS, 6, 558)
    closed = PhaseEstimation(Molecule(2.6), 4, STEPS).shares()
    assert [p.length for p in made.points] == [2.6] and made.points[0].phase == lowest_strong_peak(closed, 4)


def test_the_defaults_of_a_run_are_those_of_the_stored_run():
    run = Curve.stored()
    assert (run.bits, run.steps, tuple(p.length for p in run.points)) == (BITS, STEPS, LENGTHS)
