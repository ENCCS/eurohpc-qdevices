"""examples/hamiltonian, the curve of H2: the stored numbers, their tables and the rule, with the standard library."""

import dataclasses
import hashlib
import json
import shutil
import sys
from pathlib import Path

import pytest
from test_scan import dates

ROOT = Path(__file__).resolve().parent.parent
HERE = ROOT / "examples" / "hamiltonian"
sys.path[:0] = [str(HERE), str(ROOT / "examples" / "tools")]
import hydrogen  # noqa: E402
from hydrogen import STORED, STRONG, Curve, lowest_strong_peak, stored_numbers  # noqa: E402
from reference import EQUILIBRIUM, KCAL, NAMES, STRETCHED, Reference, Row, bases, methods  # noqa: E402

DIGEST = "2d16c76109ca27decc65d40c4aa64a64419360042fcc616bd8b39f7dbb5abbe6"
BOUND = 2e-6                    # the interpolation of the published rows is good to this: see the leave-one-out test
ROUNDED = 1.01e-8               # two numbers stored to 8 decimals


@pytest.fixture(scope="module")
def reference():
    return Reference.load()


def test_the_stored_file_keeps_its_digest():
    """Any changed byte fails here, in every environment. A deliberate new run updates the digest with it."""
    assert hashlib.sha256(STORED.read_bytes()).hexdigest() == DIGEST


def test_the_file_holds_no_date_and_nothing_of_the_machine():
    text = STORED.read_text(encoding="utf-8")
    assert dates(text) == []
    held = json.loads(text)
    assert set(held) == {"pyscf", "published", "emulated"}
    assert set(held["pyscf"]) == {"version", "bohr_in_angstrom", "decimals", "lengths_angstrom", "bases"}


def test_each_basis_has_its_spin_orbitals_and_the_version_of_pyscf_is_kept(reference):
    assert {basis: held["spin_orbitals"] for basis, held in reference.bases.items()} == {
        "sto-3g": 4, "6-31g": 8, "cc-pvdz": 20, "cc-pvtz": 56, "cc-pvqz": 120}
    assert set(NAMES) == set(reference.bases)
    assert stored_numbers()["pyscf"]["version"] == "2.14.0"
    assert len(reference.lengths) == 24


def test_fci_is_never_above_restricted_hartree_fock(reference):
    for basis in reference.bases:
        for r in reference.lengths:
            assert reference.fci(basis, r) < reference.hartree_fock(basis, r)


def test_the_published_rows_are_as_printed(reference):
    held = stored_numbers()["published"]
    assert "Phys. Rev. A 82, 032509" in held["citation"] and "arXiv:1007.0322" in held["citation"]
    assert "text layer of Table IV" in held["what"]
    assert len(reference.rows) == 82 and [row.bohr for row in reference.rows] == sorted(r.bohr for r in reference.rows)
    rows = {row.bohr: row for row in reference.rows}
    assert rows[1.4] == Row(1.4, -1.1744757142204434, 5e-16)
    assert rows[0.1] == Row(0.1, 7.127216731132, 5.5e-12)
    assert rows[20.0] == Row(20.0, -1.0000001067401283, 0.0)
    assert reference.minimum == Row(1.4011, -1.1744759314002167, 3e-16)


def test_the_interpolation_finds_a_row_that_is_left_out(reference):
    inside = [row for row in reference.rows if 0.35 <= row.bohr * reference.bohr <= 4.0]
    assert len(inside) == 59
    for row in inside:
        others = dataclasses.replace(reference, rows=tuple(r for r in reference.rows if r is not row))
        assert others.published(row.bohr * reference.bohr) == pytest.approx(row.energy, abs=BOUND)
    assert reference.published(EQUILIBRIUM) == pytest.approx(reference.minimum.energy, abs=1e-9)


def test_the_points_of_the_chart_are_the_published_rows_in_its_window(reference):
    points = reference.points(0.35, 4.0)
    assert min(length for length, _ in points) == pytest.approx(0.8 * reference.bohr)
    assert max(length for length, _ in points) == pytest.approx(7.0 * reference.bohr)
    assert (1.4 * reference.bohr, -1.1744757142204434) in points and len(points) == 28


def test_the_published_values_lie_below_every_fci_curve_within_their_accuracy(reference):
    stated = max(row.stated for row in reference.rows)
    for basis in reference.bases:
        for r in reference.lengths:
            assert reference.published(r) - stated - BOUND < reference.fci(basis, r)


def test_a_larger_basis_can_lie_higher_at_a_short_bond(reference):
    rises = [r for r in reference.lengths if reference.fci("cc-pvdz", r) > reference.fci("6-31g", r)]
    assert rises == [0.35, 0.4, 0.45]


def test_exact_in_sto_3g_lies_0_037_above_the_published_energy_at_equilibrium(reference):
    above = reference.fci("sto-3g", EQUILIBRIUM) - reference.published(EQUILIBRIUM)
    assert above == pytest.approx(0.03721, abs=5e-6)
    assert above * KCAL == pytest.approx(23.35, abs=5e-3)


def test_only_the_largest_basis_comes_within_one_kcal_per_mol_at_equilibrium_and_along_the_curve(reference):
    gaps = {basis: reference.fci(basis, EQUILIBRIUM) - reference.published(EQUILIBRIUM) for basis in reference.bases}
    worst = {basis: max(reference.fci(basis, r) - reference.published(r) for r in reference.lengths)
             for basis in reference.bases}
    assert [basis for basis, gap in gaps.items() if gap * KCAL < 1] == ["cc-pvqz"]
    assert [basis for basis, gap in worst.items() if gap * KCAL < 1] == ["cc-pvqz"]


def test_the_table_of_methods_holds_each_row_at_both_lengths():
    table = methods(Curve.stored()).splitlines()
    assert len(table) == 8 and f"at {EQUILIBRIUM} angstrom" in table[0] and f"at {STRETCHED} angstrom" in table[0]
    rows = {"restricted Hartree-Fock, STO-3G": [-1.1167, 0.0578, 36.3, -0.6560, 0.3453, 216.7],
            "exact in STO-3G: FCI": [-1.1373, 0.0372, 23.3, -0.9336, 0.0677, 42.5],
            "phase estimation in STO-3G, 8 bits": [-1.1270, 0.0475, 29.8, -0.9281, 0.0733, 46.0],
            "restricted Hartree-Fock, cc-pVQZ": [-1.1335, 0.0410, 25.7, -0.8333, 0.1680, 105.4],
            "FCI, cc-pVQZ": [-1.1738, 0.0007, 0.4, -1.0011, 0.0003, 0.2]}
    for name, row in rows.items():
        line = next(line for line in table if line.startswith(name))
        assert [float(x) for x in line[len(name):].split()] == row
    assert table[-1].split()[-2:] == ["-1.1745", "-1.0014"]
    stretched = methods(Curve.stored(), (EQUILIBRIUM, 2.6)).splitlines()         # where the top reading is wrong
    assert next(line for line in stretched if line.startswith("phase estimation")).split()[9] == "-0.9255"


def test_the_table_of_bases_holds_each_row():
    sizes = bases().splitlines()
    assert [line.split() for line in sizes[3:]] == [
        ["STO-3G", "4", "6", "0.03721", "23.35", "0.08188", "51.38"],
        ["6-31G", "8", "28", "0.02279", "14.30", "0.03545", "22.25"],
        ["cc-pVDZ", "20", "190", "0.01106", "6.94", "0.04933", "30.95"],
        ["cc-pVTZ", "56", "1540", "0.00214", "1.34", "0.00671", "4.21"],
        ["cc-pVQZ", "120", "7140", "0.00068", "0.43", "0.00137", "0.86"]]


def test_the_rule_reads_the_lowest_strong_peak_and_no_weak_one():
    size = 2 ** 4
    assert STRONG == 0.1
    both = {3 / size: 0.45, 11 / size: 0.55}
    assert lowest_strong_peak(both, 4) == 11 / size                 # the larger phase is the lower energy
    weak = {3 / size: 0.92, 14 / size: 0.08}
    assert lowest_strong_peak(weak, 4) == 3 / size
    slope = {5 / size: 0.6, 6 / size: 0.3, 7 / size: 0.1}
    assert lowest_strong_peak(slope, 4) == 5 / size                 # a shoulder of a peak is not a peak
    with pytest.raises(ValueError, match="empty"):
        lowest_strong_peak({m / size: 1 / size for m in range(size - 1)} | {15 / size: 0.09}, 4)


def test_the_rule_looks_round_the_end_of_the_grid():
    size = 2 ** 4
    assert lowest_strong_peak({15 / size: 0.3, 0.0: 0.5, 5 / size: 0.2}, 4) == 5 / size


def test_the_stored_run_reads_within_half_a_grid_step_and_its_top_reading_can_be_the_wrong_level():
    run = Curve.stored()
    assert (run.bits, run.steps, run.qubits, run.gates) == (8, 3, 10, 9248)
    assert run.grid == pytest.approx(0.02454, abs=5e-6)
    for point in run.points:
        assert abs(point.energy - point.exact) <= run.grid / 2 + 1e-3   # the product formula shifts by under 1e-3
    assert {point.length for point in run.points if abs(point.top - point.exact) > 0.5} == {2.6, 4.0}
    assert run.at(2.6).overlap == pytest.approx(0.579, abs=5e-4)
    assert run.at(2.6).length == 2.6 and len(run.table().splitlines()) == len(run.points) + 2


def test_exact_in_sto_3g_is_the_block_where_a_run_stores_it(reference):
    points = Curve.stored().points
    assert {point.length for point in points} <= set(reference.lengths)
    for point in points:
        assert point.exact == pytest.approx(reference.fci("sto-3g", point.length), abs=ROUNDED)


def test_a_run_is_stored_read_back_and_the_other_keys_stay(tmp_path, monkeypatch):
    copy = tmp_path / STORED.name
    shutil.copy(STORED, copy)
    monkeypatch.setattr(hydrogen, "STORED", copy)
    run, before = Curve.stored(), stored_numbers()
    dataclasses.replace(run, gates=1).store()
    assert Curve.stored().gates == 1 and Curve.stored().points == run.points
    after = stored_numbers()
    assert after["pyscf"] == before["pyscf"] and after["published"] == before["published"]
    run.store()
    assert copy.read_bytes() == STORED.read_bytes()


def test_the_table_of_the_stored_run_holds_its_columns():
    rows = Curve.stored().table().splitlines()
    assert rows[0] == "8 bits, 3 steps per unit time: 10 qubits, 9248 two-qubit gates, grid step 0.025 hartree"
    assert rows[7].split() == ["2.6", "-0.9352", "0.579", "-0.925", "0.336", "-0.361", "0.363"]
    assert rows[9].split() == ["4.0", "-0.9332", "0.504", "-0.923", "0.280", "-0.285", "0.409"]
