"""examples/hamiltonian, the curve of H2: the tables and the charts of the tutorial, by the values they show."""

import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("scipy")
matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "examples" / "hamiltonian"), str(ROOT / "examples" / "tools")]
from figures import REACH, dissociation, overlaps  # noqa: E402
from hydrogen import Curve  # noqa: E402
from molecule import Molecule  # noqa: E402
from reference import Reference  # noqa: E402
from tables import against_closed_form, more_bits, readings, well  # noqa: E402


@pytest.fixture(scope="module")
def reference():
    return Reference.load()


@pytest.fixture
def chart():
    """The chart of the curve, and the plot of each label on it."""
    ax = dissociation(Curve.stored()).axes[0]
    yield ax, {line.get_label(): line for line in ax.lines}
    matplotlib.pyplot.close("all")


def test_readings_shows_the_top_reading_and_the_rule_at_each_size():
    rows = readings().splitlines()
    assert rows[0] == "At 2.6 angstrom: exact energy -0.935, squared overlap 0.579."
    assert [row.split() for row in rows[2:]] == [["6", "-0.975", "-0.975"], ["7", "-0.925", "-0.925"],
                                                 ["8", "-0.361", "-0.925"], ["9", "-0.938", "-0.938"],
                                                 ["10", "-0.355", "-0.938"]]


def test_well_shows_both_minima_and_how_much_too_deep_sto_3g_is():
    rows = well().splitlines()
    assert rows[1].split()[-3:] == ["0.7349", "-1.1373", "0.2041"]
    assert rows[2].split()[-3:] == ["0.7414", "-1.1745", "0.1745"]
    assert rows[3] == "STO-3G is too deep by 0.0297 hartree, 18.6 kcal/mol"
    assert len(rows) == 4


def test_against_closed_form_shows_each_length_of_the_stored_run():
    rows = against_closed_form(Curve.stored()).splitlines()
    assert rows[0].split()[:3] == ["length", "reading,", "gates"] and rows[0].count("closed form") == 2
    assert [row.split() for row in rows[1:]] == [
        ["0.5", "-1.0524", "-1.0524", "0.9705", "0.9699", "+0.00062"],
        ["0.7414", "-1.1270", "-1.1270", "0.5681", "0.5680", "+0.00047"],
        ["1.1", "-1.0897", "-1.0897", "0.4795", "0.4796", "+0.00032"],
        ["1.4", "-1.0210", "-1.0210", "0.7492", "0.7486", "+0.00022"],
        ["1.8", "-0.9577", "-0.9577", "0.7121", "0.7116", "+0.00010"],
        ["2.6", "-0.9255", "-0.9255", "0.3361", "0.3361", "+0.00001"],
        ["3.0", "-0.9281", "-0.9281", "0.4530", "0.4527", "+0.00000"],
        ["4.0", "-0.9231", "-0.9231", "0.2796", "0.2796", "+0.00000"]]


def test_more_bits_near_exact_in_sto_3g_and_not_the_published_energy():
    assert [row.split() for row in more_bits().splitlines()[1:]] == [
        ["6", "0.09817", "-1.15157", "-0.01430", "+0.02291"],
        ["8", "0.02454", "-1.12702", "+0.01025", "+0.04745"],
        ["10", "0.00614", "-1.13929", "-0.00202", "+0.03518"],
        ["12", "0.00153", "-1.13623", "+0.00104", "+0.03825"],
        ["14", "0.00038", "-1.13661", "+0.00066", "+0.03787"],
        ["16", "0.00010", "-1.13680", "+0.00047", "+0.03767"]]


def test_the_chart_draws_each_line_of_sto_3g_from_the_block(chart):
    _, lines = chart
    grey, blue = lines["restricted Hartree-Fock, STO-3G"], lines["exact in STO-3G (FCI)"]
    for k in (0, 57, 199):
        r = float(grey.get_xdata()[k])
        assert grey.get_ydata()[k] == pytest.approx(Molecule(r).hartree_fock)
        assert blue.get_ydata()[k] == pytest.approx(Molecule(r).exact)
    assert (grey.get_xdata()[0], grey.get_xdata()[-1]) == REACH


def test_the_chart_draws_the_large_basis_and_the_published_points_from_the_file(chart, reference):
    _, lines = chart
    teal, dots = lines["FCI, cc-pVQZ"], lines["published, complete basis"]
    assert list(teal.get_xdata()) == list(reference.lengths)
    assert list(teal.get_ydata()) == [reference.fci("cc-pvqz", r) for r in reference.lengths]
    assert list(zip(dots.get_xdata(), dots.get_ydata(), strict=True)) == reference.points(*REACH)


def test_the_chart_draws_each_reading_with_half_a_grid_step_either_way(chart):
    ax, _ = chart
    run, marks = Curve.stored(), ax.containers[0]
    assert marks.get_label() == "phase estimation in STO-3G, 8 bits, emulated"
    assert list(marks.lines[0].get_ydata()) == [point.energy for point in run.points]
    for point, segment in zip(run.points, marks.lines[2][0].get_segments(), strict=True):
        assert list(segment[:, 1]) == pytest.approx([point.energy - run.grid / 2, point.energy + run.grid / 2])


def test_the_chart_of_overlaps_draws_the_overlap():
    line = overlaps().axes[0].lines[0]
    assert line.get_ydata()[0] == pytest.approx(Molecule(REACH[0]).overlap)
    assert line.get_ydata()[-1] == pytest.approx(Molecule(REACH[1]).overlap)
    matplotlib.pyplot.close("all")


def test_the_chart_covers_the_stored_lengths():
    assert REACH == (0.35, 4.0)
