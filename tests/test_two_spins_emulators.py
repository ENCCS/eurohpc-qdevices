"""examples/hamiltonian/two_spins with QuTiP and Qrisp: the numbers the notebook quotes, the texts and the README.

`pixi run --manifest-path examples/qrisp/pixi.toml pytest -q tests/test_two_spins_emulators.py`; skipped without them.
"""

import json
import sys
from math import sin
from pathlib import Path

import pytest

pytest.importorskip("qutip")
EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
HERE = EXAMPLES / "hamiltonian" / "two_spins"
sys.path[:0] = [str(HERE), str(EXAMPLES / "tools"), str(EXAMPLES / "qrisp")]
import spins  # noqa: E402
from circuit import circuit_of  # noqa: E402
from trotter import T  # noqa: E402

JOBS = {job["name"]: job for job in json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))["jobs"]}


def test_the_levels_and_the_exact_answer_at_the_time_of_the_jobs():
    assert spins.hamiltonian().eigenenergies() == pytest.approx([-2.6, -1, 1, 2.6])
    exact = spins.exact()
    assert exact["11"] == pytest.approx(sin(T / 2) ** 2) and round(exact["11"], 3) == 0.874
    assert exact["01"] == pytest.approx(0, abs=1e-12) and exact["10"] == pytest.approx(0, abs=1e-12)


def test_the_solver_agrees_with_the_propagator_and_11_peaks_at_the_time_of_the_jobs():
    times = [i * 2 * T / 400 for i in range(401)]
    curves = spins.over_time(times)
    assert {key: round(float(c[200]), 6) for key, c in curves.items()} == {
        key: round(v, 6) for key, v in spins.exact().items()}
    assert max(range(401), key=lambda i: curves["11"][i]) == 200


@pytest.mark.parametrize(("steps", "norm"), [(5, 0.236), (16, 0.021)])
def test_qutip_gives_the_shares_of_each_text_and_the_error_of_its_steps(steps, norm):
    text = circuit_of(HERE / JOBS[f"STEPS{steps}"]["file"]).shares()
    assert spins.trotter(steps) == pytest.approx(text, abs=1e-12)
    assert round(spins.error(steps), 3) == norm


def test_the_gates_of_a_step_equal_the_exponentials():
    assert max(spins.gates_against_exponentials()) < 1e-12


def test_the_cx_count_test_gives_the_known_answers_and_2_for_the_steps():
    swap = spins.qt.Qobj([[1, 0, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], dims=[[2, 2], [2, 2]])
    cx = spins.qt.Qobj([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dims=[[2, 2], [2, 2]])
    local = spins.qt.tensor(spins.qt.sigmax(), (-0.3j * spins.qt.sigmay()).expm())
    hadamards = spins.qt.tensor(spins.qt.sigmax() + spins.qt.sigmaz(), spins.qt.sigmax() + spins.qt.sigmaz()) / 2
    assert [spins.cx_needed(u) for u in (local, cx, cx * hadamards * cx, swap)] == [0, 1, 2, 3]
    assert [spins.cx_needed(spins.product(n)) for n in (5, 16)] == [2, 2]
    assert spins.cx_needed((-1j * spins.hamiltonian() * T).expm()) == 2


def test_qrisp_writes_the_texts_of_the_folder_and_its_emulator_agrees():
    pytest.importorskip("qrisp")
    from by_qrisp import emulated, sha256, text

    assert text(5).encode("utf-8") == (HERE / "STEPS5.qasm").read_bytes()
    assert sha256(text(16)) == JOBS["STEPS16"]["sha256"]
    assert emulated(5) == pytest.approx(circuit_of(HERE / "STEPS5.qasm").shares(), abs=1e-5)


def test_the_readme_is_what_the_writer_writes():
    pytest.importorskip("qrisp")
    from write_two_spins import PAGE

    assert (HERE / "README.md").read_text(encoding="utf-8") == PAGE.text("hamiltonian/two_spins")
