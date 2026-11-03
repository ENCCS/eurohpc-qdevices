"""examples/tools/pictures.py: a circuit of each form of text drawn, and the bars of each source of a folder.

With matplotlib and qutip-qip: `pixi run --manifest-path examples/qrisp/pixi.toml pytest -q tests/test_pictures.py`.
Also write_pictures.py, on one folder into a temporary folder.
"""

import platform
import re
import shutil
import sys
from math import sqrt
from pathlib import Path

import pytest

matplotlib = pytest.importorskip("matplotlib")
pytest.importorskip("qutip_qip")
matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.container import BarContainer  # noqa: E402
from matplotlib.patches import Arc  # noqa: E402

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
import write_pictures  # noqa: E402
from circuit import circuit_of  # noqa: E402
from pictures import SOURCES, Outcome, circuit_figure, folder_outcomes, outcomes_figure  # noqa: E402
from test_picture_files import EACH, SIGNATURE, chunks  # noqa: E402
from write_pictures import WIDEST, fitted_figure  # noqa: E402

TWO_SPINS = EXAMPLES / "hamiltonian" / "two_spins"
FORMS = {"OpenQASM 2": "euroqexa-bell/BELL.qasm", "OpenQASM 3": "vlq-bell/BELL.qasm",
         "the broker's list": "piastq-native/NATIVE.json", "two spins": "hamiltonian/two_spins/STEPS5.qasm"}


@pytest.fixture(autouse=True)
def closed():
    yield
    plt.close("all")


def meters(fig) -> int:
    """The measurements drawn: one arc each."""
    return sum(isinstance(patch, Arc) for patch in fig.axes[0].patches)


@pytest.mark.parametrize("path", FORMS.values(), ids=FORMS.keys())
def test_each_form_of_text_is_drawn_with_its_measured_qubits_marked(path):
    circuit = circuit_of(EXAMPLES / path)
    fig = circuit_figure(circuit, most=12, title="T")
    assert meters(fig) == len(circuit.bits)
    title = fig.axes[0].get_title()
    assert title.startswith("T: ") and (("first 12 of" in title) == (len(circuit.ops) > 12))
    width, height = fig.get_size_inches()
    assert 1 < width < 20 and 1 < height < 30


def test_a_small_circuit_has_all_its_gates_and_a_plain_title():
    fig = circuit_figure(circuit_of(EXAMPLES / "euroqexa-bell" / "BELL.qasm"))
    assert fig.axes[0].get_title() == "2 gates" and meters(fig) == 2


def test_a_circuit_of_25_qubits_is_cut_and_says_so():
    circuit = circuit_of(EXAMPLES / "qrisp" / "hello" / "HELLO.qasm")
    assert len(circuit.bits) == 25
    fig = circuit_figure(circuit, most=5)
    assert fig.axes[0].get_title() == f"the first 5 of {len(circuit.ops)} gates, then the measurements"
    assert meters(fig) == 25


def bars(fig) -> list:
    """One container of bars for each source."""
    return [c for c in fig.axes[0].containers if isinstance(c, BarContainer)]


def labels(fig) -> list:
    return [text.get_text() for text in fig.axes[0].get_legend().get_texts()]


def test_one_job_gives_each_key_from_each_stored_source_and_the_machine():
    outcomes = folder_outcomes(TWO_SPINS)
    assert [o.name for o in outcomes] == ["STEPS5", "STEPS16"]
    fig = outcomes_figure(outcomes[:1])
    assert labels(fig) == [label for label, _ in SOURCES]
    assert [t.get_text() for t in fig.axes[0].get_xticklabels()] == ["11", "00", "01", "10"]
    assert [len(c) for c in bars(fig)] == [4, 4, 4, 4]


def test_the_shot_error_of_the_machine_is_the_binomial_standard_error():
    fig = outcomes_figure(folder_outcomes(TWO_SPINS)[:1])
    machine = bars(fig)[-1]
    low, high = machine.errorbar.lines[2][0].get_segments()[0][:, 1]
    assert (high - low) / 2 == pytest.approx(sqrt(0.783 * 0.217 / 1000))
    assert machine.patches[0].get_height() == pytest.approx(0.783)


def test_several_jobs_give_the_top_key_of_each():
    fig = outcomes_figure(folder_outcomes(TWO_SPINS))
    assert [t.get_text() for t in fig.axes[0].get_xticklabels()] == ["STEPS5\n11", "STEPS16\n11"]
    assert [round(p.get_height(), 3) for p in bars(fig)[-1].patches] == [0.783, 0.789]


def test_a_missing_source_is_left_out(tmp_path):
    for name in ("manifest.json", "STEPS5.qasm", "STEPS16.qasm", "results.json"):
        shutil.copy(TWO_SPINS / name, tmp_path / name)
    assert labels(outcomes_figure(folder_outcomes(tmp_path))) == [SOURCES[0][0], SOURCES[3][0]]
    (tmp_path / "results.json").unlink()
    fig = outcomes_figure(folder_outcomes(tmp_path))
    assert labels(fig) == [SOURCES[0][0]] and bars(fig)[0].errorbar is None


def test_more_than_six_keys_sum_the_rest_as_other():
    counts = {format(i, "03b"): n for i, n in enumerate((400, 20, 30, 40, 50, 60, 70, 330))}
    fig = outcomes_figure([Outcome("GHZ", {"000": 0.5, "111": 0.5}, counts=counts)])
    ticks = [t.get_text() for t in fig.axes[0].get_xticklabels()]
    assert len(ticks) == 7 and ticks[:2] == ["000", "111"] and ticks[-1] == "other"
    machine = bars(fig)[-1].patches
    assert machine[-1].get_height() == pytest.approx((20 + 30) / 1000)


def test_the_house_colours_follow_the_source_and_not_its_place(tmp_path):
    for name in ("manifest.json", "STEPS5.qasm", "STEPS16.qasm", "results.json"):
        shutil.copy(TWO_SPINS / name, tmp_path / name)
    fig = outcomes_figure(folder_outcomes(tmp_path))
    colours = [matplotlib.colors.to_hex(c.patches[0].get_facecolor()) for c in bars(fig)]
    assert colours == [SOURCES[0][1], SOURCES[3][1]]


def wires(fig) -> list:
    """The label of each wire, from the bottom: the classical wires, then the qubits."""
    return [t.get_text() for t in fig.axes[0].texts if re.fullmatch(r"\$[cq](_\{\d+\})?\$", t.get_text())]


def test_idle_qubits_are_not_drawn_and_the_title_says_so():
    fig = circuit_figure(circuit_of(EXAMPLES / "vlq-bell" / "BELL.qasm"), title="BELL")
    assert fig.axes[0].get_title() == "BELL: 6 gates; idle qubits not drawn"
    assert wires(fig) == ["$c_{0}$", "$c_{1}$", "$q_{0}$", "$q_{1}$", "$q_{24}$"]


def test_many_bits_share_one_classical_wire_and_one_gate_is_singular():
    fig = circuit_figure(circuit_of(EXAMPLES / "qrisp" / "hello" / "HELLO.qasm"))
    assert wires(fig) == ["$c$", *(f"$q_{{{q}}}$" for q in range(25))] and meters(fig) == 25
    assert circuit_figure(circuit_of(EXAMPLES / "euroqexa-one-qubit" / "X.qasm")).axes[0].get_title() == "1 gate"


def test_a_long_circuit_is_cut_to_fit_and_a_cut_that_narrows_nothing_is_not_made():
    shor = fitted_figure(circuit_of(EXAMPLES / "qrisp" / "shor13" / "SHOR13.qasm"), "SHOR13")
    assert shor.get_size_inches()[0] <= WIDEST and shor.axes[0].get_title().startswith("SHOR13: the first ")
    hello = fitted_figure(circuit_of(EXAMPLES / "qrisp" / "hello" / "HELLO.qasm"), "HELLO")
    assert hello.axes[0].get_title() == "HELLO: 13 gates" and hello.get_size_inches()[0] > WIDEST


def test_the_broker_list_has_no_classical_bits_so_its_picture_has_one_classical_wire():
    native = circuit_of(EXAMPLES / "piastq-native" / "NATIVE.json")
    assert wires(circuit_figure(native, one_wire=True)) == ["$c$", "$q_{0}$", "$q_{1}$"]
    job = write_pictures.drawn_job(EXAMPLES / "piastq-bell")
    assert job["file"] == "BELL.json" and wires(write_pictures.figures(EXAMPLES / "piastq-bell")[0])[0] == "$c$"


def test_a_folder_draws_the_job_its_readme_describes_and_a_cut_keeps_whole_steps():
    assert write_pictures.drawn_job(EXAMPLES / "hamiltonian" / "state_transfer")["name"] == "MAIN"
    assert write_pictures.drawn_job(EXAMPLES / "euroqexa-three-jobs")["name"] == "BELL"
    assert write_pictures.drawn_job(EXAMPLES / "euroqexa-bell")["name"] == "BELL"
    steps = write_pictures.figures(TWO_SPINS)[0]
    assert steps.axes[0].get_title() == "STEPS5: the first 18 of 45 gates, then the measurements"   # two steps of 9


def rotations(fig) -> set:
    return {label.get_rotation() for label in fig.axes[0].get_xticklabels()}


def test_long_keys_stand_upright_and_many_jobs_widen_the_chart():
    assert rotations(outcomes_figure(folder_outcomes(EXAMPLES / "qrisp" / "hello"))) == {90.0}
    chain = outcomes_figure(folder_outcomes(EXAMPLES / "hamiltonian" / "state_transfer"))
    assert len(chain.axes[0].get_xticklabels()) == 11 and chain.get_size_inches()[0] > 6.4
    two = outcomes_figure(folder_outcomes(TWO_SPINS))
    assert rotations(two) == {0.0} and tuple(two.get_size_inches()) == (6.4, 3.4)


def test_the_writer_draws_one_folder_into_another_and_leaves_the_folder_as_it_was(tmp_path):
    folder = EXAMPLES / "euroqexa-bell"
    before = {f.name: f.read_bytes() for f in folder.iterdir() if f.is_file()}
    assert write_pictures.main([str(folder), "--out", str(tmp_path)]) == 0
    assert sorted(p.name for p in (tmp_path / "euroqexa-bell").iterdir()) == ["circuit.png", "outcomes.png"]
    for name in ("circuit.png", "outcomes.png"):
        data = (tmp_path / "euroqexa-bell" / name).read_bytes()
        assert data.startswith(SIGNATURE) and len(data) < EACH, name
        assert not {kind for kind, _ in chunks(data)} & {"tEXt", "iTXt", "zTXt", "tIME"}, name
    assert {f.name: f.read_bytes() for f in folder.iterdir() if f.is_file()} == before


@pytest.mark.parametrize("name", ["euroqexa-bell", "hamiltonian/two_spins"])
def test_the_pictures_of_a_folder_are_up_to_date(tmp_path, name):
    """Byte for byte where the pictures were made; fonts differ between other machines."""
    if (sys.platform, platform.machine()) != ("darwin", "arm64"):
        pytest.skip("the pictures were drawn on an Apple Silicon Mac")
    assert write_pictures.main([str(EXAMPLES / name), "--out", str(tmp_path)]) == 0
    for picture in ("circuit.png", "outcomes.png"):
        drawn = (tmp_path / name / picture).read_bytes()
        assert drawn == (EXAMPLES / name / picture).read_bytes(), f"{name}/{picture}: run the task pictures again"
