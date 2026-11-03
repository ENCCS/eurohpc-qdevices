"""The path through QuTiP: each gate as a unitary, the order of a key, one folder end to end. It needs qutip-qip."""

import hashlib
import json
import platform
import sys
from pathlib import Path

import pytest
from test_qrisp_emulator_path import ANGLES, CalledModules, our_unitary
from test_scan import BANNED

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from circuit import Circuit, circuit_of  # noqa: E402
from emulate import QUTIP_FILE  # noqa: E402
from gates import ONE, TWO  # noqa: E402
from overview import example_folders  # noqa: E402

JOBS = [(folder, job) for folder in example_folders(EXAMPLES)
        for job in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"]]
ASYMMETRIC = ("qreg q[3];\ncreg c[3];\nry(0.6) q[0];\nx q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n"
              "measure q[2] -> c[2];\n")


def qutip_module():
    """The new module, when qutip-qip is here."""
    pytest.importorskip("qutip_qip")
    import qutip_emulator

    return qutip_emulator


def known(emulator) -> set:
    """Each gate of ours that has a way into qutip-qip."""
    return (set(emulator.ONE_QUBIT) | set(emulator.CONTROLLED) | set(emulator.TWO_QUBIT)
            | set(emulator.BUILT_FROM_OTHERS))


def test_every_gate_of_ours_and_every_gate_in_the_texts_has_a_way_into_qutip():
    emulator = qutip_module()
    used = {name for folder, job in JOBS for name, _, _ in circuit_of(folder / job["file"]).ops}
    assert known(emulator) == set(ONE) | set(TWO)
    assert used <= known(emulator)


@pytest.mark.parametrize(("name", "size"), [*((name, 1) for name in ONE), *((name, 2) for name in TWO)])
def test_each_gate_in_qutip_equals_ours_as_a_unitary_up_to_a_global_phase(name, size):
    emulator = qutip_module()
    np = pytest.importorskip("numpy")
    qc = emulator.QubitCircuit(size)
    emulator.add_gate(qc, name, (0, 1)[:size], ANGLES.get(name, ()))
    theirs, ours = qc.compute_unitary().full(), our_unitary(name, size)
    if size == 2:                                # QuTiP's matrix holds qubit 0 as its highest bit
        swap = [0, 2, 1, 3]
        theirs = theirs[swap][:, swap]
    overlap = np.trace(ours.conj().T @ theirs) / 2 ** size
    assert abs(overlap) == pytest.approx(1, abs=1e-12)
    assert np.abs(theirs - overlap * ours).max() < 1e-12


def test_qubit_zero_is_the_highest_bit_of_an_index_into_the_state():
    emulator = qutip_module()
    np = pytest.importorskip("numpy")
    probabilities = np.zeros(8)
    probabilities[0b100] = 1.0                   # qubit 0 reads 1, qubits 1 and 2 read 0
    assert emulator.keys_of(probabilities, (2, 1, 0)) == {"001": 1.0}
    assert emulator.keys_of(probabilities, (0,)) == {"1": 1.0}


def test_the_keys_of_an_asymmetric_circuit_are_ours_in_our_order():
    emulator = qutip_module()
    circuit = Circuit.of_text(ASYMMETRIC)
    theirs, ours = emulator.qutip_shares(circuit), circuit.shares()
    assert set(theirs) == set(ours) == {"010", "011"}
    assert all(theirs[key] == pytest.approx(ours[key], abs=1e-15) for key in ours)
    assert theirs["011"] == pytest.approx(0.0873322, abs=1e-7)       # sin(0.3) squared: q[0] reads 1


def test_a_qubit_not_read_is_summed_over_and_the_broker_reads_qubit_zero_first():
    emulator = qutip_module()
    text = "qreg q[3];\ncreg c[2];\nx q[0];\nh q[1];\nmeasure q[0] -> c[0];\nmeasure q[2] -> c[1];\n"
    assert emulator.qutip_shares(Circuit.of_text(text)) == {"01": pytest.approx(1.0)}
    native = circuit_of(EXAMPLES / "piastq-native" / "NATIVE.json")
    theirs = emulator.qutip_shares(native)
    assert all(theirs[key] == pytest.approx(share, abs=1e-15) for key, share in native.shares().items())


def test_a_job_qutip_cannot_run_is_named_in_the_file_with_why(monkeypatch):
    emulator = qutip_module()
    from write_qutip_emulated import stored_text

    monkeypatch.delitem(emulator.ONE_QUBIT, "x")
    held = json.loads(stored_text(EXAMPLES / "euroqexa-three-jobs"))
    assert list(held["jobs"]) == ["BELL", "BELL_AGAIN"]
    assert held["not_run"] == {"X": "no qutip-qip gate for: x"}


def test_a_run_of_qutip_gives_the_stored_file_of_a_small_folder():
    """Byte for byte where the files were made; elsewhere within one unit of the 8th place."""
    qutip_module()
    from write_qutip_emulated import stored_text

    folder = EXAMPLES / "hamiltonian" / "state_transfer"
    rebuilt = stored_text(folder)
    if (sys.platform, platform.machine()) == ("darwin", "arm64"):
        assert rebuilt.encode("utf-8") == (folder / QUTIP_FILE).read_bytes()
    else:
        held = json.loads((folder / QUTIP_FILE).read_text(encoding="utf-8"))
        for name, said in json.loads(rebuilt)["jobs"].items():
            assert said == pytest.approx(held["jobs"][name], abs=1e-8)


def test_the_path_through_qutip_calls_nothing_on_the_scan_list():
    """Importing QuTiP loads more than it runs; here nothing on the scan's list runs, in the folders under 25 qubits.

    QuTiP runs only the qubits a job uses, so only qrisp/hello, which uses all 25, is left out."""
    emulator = qutip_module()
    wide = {folder for folder, job in JOBS if emulator.qutip_circuit(circuit_of(folder / job["file"])).N >= 25}
    small = [folder for folder in example_folders(EXAMPLES) if folder not in wide]
    with CalledModules() as called:
        for folder in small:
            emulator.folder_shares(folder)
    assert {folder.name for folder in wide} == {"hello"}
    assert hashlib.sha256(b"qutip").hexdigest() in called.heads()          # the watch does see what runs
    assert not called.heads() & {head for head, _, _ in BANNED}
