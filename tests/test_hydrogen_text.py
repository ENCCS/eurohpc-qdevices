"""examples/hamiltonian, the curve of H2: the digits that the text of each cell types, against the public functions."""

import sys
from math import comb, pi
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "examples" / "hamiltonian"), str(ROOT / "examples" / "tools")]
from hydrogen import STRONG, Curve, energy_of  # noqa: E402
from integrals import CONTRACTION, Integrals  # noqa: E402
from molecule import BOHR, Molecule, PhaseEstimation, atom_energy, minimum  # noqa: E402
from reference import KCAL, NEAREST, Reference  # noqa: E402

ATOM = -0.5                     # the exact energy of one hydrogen atom: Szabo and Ostlund, p. 161
LEAST = (2 / pi) ** 2           # the least share of a level at its nearest point of the grid


@pytest.fixture(scope="module")
def reference():
    return Reference.load()


def text(value: float, places: int) -> str:
    return f"{value:.{places}f}"


def above(reference, basis: str, length: float) -> float:
    return reference.fci(basis, length) - reference.published(length)


def test_the_opening_of_the_section(reference):
    zero_point = (4401.21 / 2 - 121.33 / 4) / 219474.63136  # the constants of the X state in the NIST WebBook
    assert text(zero_point * KCAL, 0) == "6"
    run = Curve.stored()
    assert (run.gates, run.bits, run.steps, len(run.points)) == (9248, 8, 3, 8)
    assert (len(CONTRACTION), reference.bases["sto-3g"]["spin_orbitals"] // 4) == (3, 1)
    assert reference.bases["cc-pvqz"]["spin_orbitals"] // 4 == 30
    assert comb(reference.bases["sto-3g"]["spin_orbitals"], 2) == 6
    inside = [row for row in reference.rows if 0.35 <= row.bohr * reference.bohr <= 4.0]
    assert max(row.stated for row in inside) < 1e-13


def test_which_peak_to_read(reference):
    assert text(Molecule(0.735).overlap, 3) == "0.988" and text(Molecule(4.0).overlap, 3) == "0.504"
    assert STRONG == 0.1 and text(LEAST, 3) == "0.405"
    assert text(min(Molecule(r).overlap for r in reference.lengths) * LEAST, 3) == "0.204"
    assert min(Molecule(r).levels(3)[0][1] for r in reference.lengths) * LEAST > 0.204


def test_a_level_above_zero_wraps_round_the_grid():
    molecule = Molecule(0.5)
    upper = molecule.levels(3)[1][0]
    assert text(upper, 4) == "0.2425" and text(upper - 2 * pi, 3) == "-6.041"
    near = round((-upper / (2 * pi)) % 1 * 256) / 256
    assert text(energy_of(near), 3) == "-6.038"
    assert text(PhaseEstimation(molecule, 8, 3).shares()[near], 4) == "0.0052"


def test_the_gap_between_the_levels():
    mesh = [round(0.35 + 0.01 * k, 2) for k in range(366)]
    gap = min(Molecule(r).levels()[1][0] - Molecule(r).levels()[0][0] for r in mesh)
    assert text(gap, 2) == "0.57"
    assert text(gap / (2 * pi / 2 ** 5), 1) == "2.9" and text(gap / (2 * pi / 2 ** 4), 1) == "1.4"
    assert text(2 * pi / 2 ** 3, 3) == "0.785"


def test_the_wrong_level_at_2_6_angstrom_and_the_table_after_it():
    molecule, run = Molecule(2.6), Curve.stored()
    assert text(molecule.overlap, 3) == "0.579" and text(molecule.exact, 3) == "-0.935"
    assert text(molecule.levels()[1][0] + molecule.nuclear, 4) == "-0.3558"
    gaps = [abs(point.share - PhaseEstimation(Molecule(point.length), run.bits, run.steps).shares()[point.phase])
            for point in run.points]
    assert text(max(gaps), 5) == "0.00057"
    assert text(run.grid, 4) == "0.0245"
    assert abs(Molecule(3.0).levels(3)[0][0] - Molecule(3.0).levels()[0][0]) < 1e-5


def test_reading_the_chart(reference):
    atoms, far = 2 * atom_energy(), Molecule(4.0).hartree_fock
    assert text(far, 4) == "-0.6149" and text(atoms, 4) == "-0.9332" and text(far - atoms, 4) == "0.3183"
    assert text(Integrals(0.0).repulsion()[0, 0, 0, 0] / 2, 4) == "0.3873"
    assert text(max(abs(p.energy - p.exact) for p in Curve.stored().points), 4) == "0.0105"
    gaps = {r: above(reference, "sto-3g", r) for r in reference.lengths}
    assert len(gaps) == 24 and min(gaps.values()) > 0
    assert (min(gaps, key=gaps.get), text(min(gaps.values()), 4)) == (0.7, "0.0370")
    assert (max(gaps, key=gaps.get), text(max(gaps.values()), 4)) == (0.35, "0.0819")


def test_the_well_of_the_chart(reference):
    lowest, atom = minimum(), atom_energy()
    assert text(lowest.length, 4) == "0.7349" and text(reference.minimum.bohr * reference.bohr, 4) == "0.7414"
    assert text(2 * atom - lowest.exact, 4) == "0.2041" and text(-1 - reference.minimum.energy, 4) == "0.1745"
    assert text(atom, 4) == "-0.4666"
    assert text(2 * (atom - ATOM), 4) == "0.0668" and text(lowest.exact - reference.minimum.energy, 4) == "0.0372"


def test_the_two_limits(reference):
    assert text(BOHR, 8) == "0.52917721" and reference.bohr == BOHR and NEAREST == 8
    assert text(reference.hartree_fock("cc-pvqz", 0.7414) - reference.published(0.7414), 4) == "0.0410"
    assert text(reference.hartree_fock("cc-pvqz", 3.0) - reference.published(3.0), 4) == "0.1680"
    assert [text(above(reference, "sto-3g", r), 4) for r in (0.7414, 3.0)] == ["0.0372", "0.0677"]
    assert [text(above(reference, "cc-pvqz", r), 4) for r in (0.7414, 3.0)] == ["0.0007", "0.0003"]


def test_more_bits_and_a_larger_basis(reference):
    read = PhaseEstimation(Molecule(0.7414), 16, 3).reading()
    assert text(read - Molecule(0.7414).exact, 5) == "0.00047"
    assert text(read - reference.published(0.7414), 5) == "0.03767"
    assert text(above(reference, "sto-3g", 0.7414), 5) == "0.03721"
    worst = {r: above(reference, "cc-pvqz", r) for r in reference.lengths}
    assert text(above(reference, "cc-pvqz", 0.7414) * KCAL, 2) == "0.43"
    assert (max(worst, key=worst.get), text(max(worst.values()) * KCAL, 2)) == (0.35, "0.86")
    assert text(above(reference, "cc-pvtz", 0.7414) * KCAL, 2) == "1.34"
    assert text(reference.fci("cc-pvdz", 0.35) - reference.fci("6-31g", 0.35), 4) == "0.0139"


def test_accuracy_and_the_size_of_the_exact_space(reference):
    depth = 2 * atom_energy() - minimum().exact
    assert text((depth - (-1 - reference.minimum.energy)) * KCAL, 1) == "18.6"
    assert text(above(reference, "sto-3g", 0.7414) * KCAL, 0) == "23"
    assert comb(reference.bases["cc-pvqz"]["spin_orbitals"], 2) == 7140 and len(reference.bases) == 5
