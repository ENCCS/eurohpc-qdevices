"""examples/hamiltonian, the curve of H2: the block from first principles, its closed form, and the rule. NumPy."""

import sys
from functools import cache
from itertools import product
from math import pi
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "examples" / "hamiltonian"), str(ROOT / "examples" / "tools")]
from hydrogen import Curve, energy_of, lowest_strong_peak  # noqa: E402
from molecule import BOHR, PAGE, Molecule, PhaseEstimation, atom_energy, difference_from_page, minimum  # noqa: E402
from reference import Reference  # noqa: E402

PAGE_DECIMALS = (8, 8, 8, 7, 7)     # the decimals that Qrisp's page prints
ROUNDED = 1.01e-8                   # two numbers stored to 8 decimals
SHARES = 1e-3                       # Qrisp's emulator drops shares under 1e-5, scales, rounds and scales again
MESH = tuple(round(0.35 + 0.01 * k, 2) for k in range(366))
FAR = tuple(round(4.0 + 0.1 * k, 1) for k in range(111))


@pytest.fixture(scope="module")
def reference():
    return Reference.load()


@cache
def at(length: float) -> Molecule:
    return Molecule(length)


@cache
def reads_the_upper_level(length: float, bits: int, steps: int | None = None) -> bool:
    molecule = at(length)
    (low, _), (high, _) = molecule.levels(steps)
    read = energy_of(lowest_strong_peak(PhaseEstimation(molecule, bits, steps).shares(), bits))
    return abs(read - low) > (high - low) / 2


def test_the_coefficients_at_0_735_angstrom_are_the_digits_of_the_page():
    made = Molecule(0.735).terms
    assert [round(value, decimals) for value, decimals in zip(made, PAGE_DECIMALS, strict=True)] == list(PAGE)
    assert max(map(abs, difference_from_page())) < 5e-9


def test_the_block_is_what_pyscf_stored_at_every_length(reference):
    assert reference.bohr == BOHR
    for r in reference.lengths:
        molecule = Molecule(r)
        assert molecule.exact == pytest.approx(reference.fci("sto-3g", r), abs=ROUNDED)
        assert molecule.hartree_fock == pytest.approx(reference.hartree_fock("sto-3g", r), abs=ROUNDED)


def test_the_two_qubit_form_holds_both_levels_of_the_block():
    x, z, one = np.array([[0, 1], [1, 0.0]]), np.diag([1.0, -1.0]), np.eye(2)
    for r in (0.5, 0.735, 2.6):
        molecule = Molecule(r)
        t = molecule.terms
        matrix = (t.identity * np.eye(4) + t.z0 * np.kron(one, z) + t.z1 * np.kron(z, one) + t.z0z1 * np.kron(z, z)
                  + t.x0x1 * np.kron(x, x))
        four = np.linalg.eigvalsh(matrix)
        assert four[[0, 3]] == pytest.approx(np.linalg.eigvalsh(molecule.block))
        start = 0b01                # q[0] = 1, q[1] = 0: index 1 in the order q[1] q[0]
        assert matrix[start, start] + molecule.nuclear == pytest.approx(molecule.hartree_fock)


def test_the_numbers_at_0_735_angstrom_are_those_of_the_text():
    molecule = Molecule(0.735)
    assert molecule.exact == pytest.approx(-1.137306, abs=5e-7)
    assert molecule.nuclear == pytest.approx(0.71997, abs=5e-6)
    assert molecule.overlap == pytest.approx(0.98756, abs=5e-6)
    assert molecule.levels(3)[0][0] - molecule.levels()[0][0] == pytest.approx(0.00047, abs=5e-6)
    assert molecule.levels(1)[0][0] - molecule.levels()[0][0] == pytest.approx(0.00444, abs=1e-5)


def test_the_product_formula_shifts_most_at_a_short_bond_and_not_at_all_at_a_long_one():
    shift = {r: Molecule(r).levels(3)[0][0] - Molecule(r).levels()[0][0] for r in (0.35, 0.735, 4.0)}
    assert shift[0.35] == pytest.approx(0.00074, abs=5e-6) and abs(shift[4.0]) < 1e-6


def test_the_top_reading_can_be_the_wrong_level_and_the_rule_reads_the_ground_level(reference):
    stretched = PhaseEstimation(Molecule(2.6), 10)
    assert stretched.top() == pytest.approx(-0.355, abs=5e-4)
    assert stretched.molecule.exact == pytest.approx(-0.935, abs=5e-4)
    assert stretched.reading() == pytest.approx(-0.938, abs=5e-4)
    for bits, r in product(range(4, 11), reference.lengths):
        estimate = PhaseEstimation(Molecule(r), bits)
        assert sum(estimate.shares().values()) == pytest.approx(1.0)
        assert abs(estimate.reading() - estimate.molecule.exact) <= pi / 2 ** bits + 1e-9


def test_the_rule_reads_the_ground_level_of_the_formula_as_well(reference):
    assert not any(reads_the_upper_level(r, bits, 3) for bits, r in product(range(4, 13), reference.lengths))


def test_with_three_bits_the_rule_goes_beyond_half_a_step_only_from_1_84_to_2_22_angstrom():
    beyond = [r for r in MESH if abs(PhaseEstimation(Molecule(r), 3).reading() - Molecule(r).exact) > pi / 8 + 1e-9]
    assert (beyond[0], beyond[-1], len(beyond)) == (1.84, 2.22, 39)


def test_four_bits_read_the_upper_level_beyond_10_angstrom_and_more_bits_do_not():
    assert not any(reads_the_upper_level(r, 4) for r in MESH)
    assert [r for r in FAR if reads_the_upper_level(r, 4)] == [round(10.2 + 0.1 * k, 1) for k in range(49)]
    assert not any(reads_the_upper_level(r, bits) for bits, r in product(range(5, 13), MESH + FAR))


def test_the_stored_run_is_what_the_closed_form_gives():
    run = Curve.stored()
    for point in run.points:
        molecule = Molecule(point.length)
        found = PhaseEstimation(molecule, run.bits, run.steps).shares()
        assert point.phase == lowest_strong_peak(found, run.bits) and point.top_phase == max(found, key=found.get)
        assert point.share == pytest.approx(found[point.phase], abs=SHARES)
        assert point.top_share == pytest.approx(found[point.top_phase], abs=SHARES)
        assert point.nuclear == pytest.approx(molecule.nuclear, abs=ROUNDED)
        assert point.overlap == pytest.approx(molecule.overlap, abs=ROUNDED)


def test_the_last_steps_of_qrisps_emulator_on_the_closed_form_give_every_stored_share():
    run = Curve.stored()
    for point in run.points:
        found = PhaseEstimation(Molecule(point.length), run.bits, run.steps).shares()
        phases, shares = zip(*found.items(), strict=True)
        kept = np.array(shares) * (np.array(shares) >= 1e-5)
        rounded = np.round(kept / kept.sum(), 5)
        made = dict(zip(phases, rounded / rounded.sum(), strict=True))
        assert made[point.phase] == pytest.approx(point.share, abs=1e-12)
        assert made[point.top_phase] == pytest.approx(point.top_share, abs=1e-12)


def test_the_well_of_sto_3g_is_deeper_than_the_published_one_though_its_energy_lies_above_it_everywhere(reference):
    lowest = minimum()
    assert lowest.length == pytest.approx(0.73487, abs=5e-5) and lowest.exact == pytest.approx(-1.137306, abs=5e-7)
    assert atom_energy() == pytest.approx(-0.46658185, abs=ROUNDED)
    depth = 2 * atom_energy() - lowest.exact
    assert depth == pytest.approx(0.20414, abs=5e-6)
    assert -1 - reference.minimum.energy == pytest.approx(0.17448, abs=5e-6)
    assert depth > -1 - reference.minimum.energy
    assert all(Molecule(r).exact > reference.published(r) for r in reference.lengths)
