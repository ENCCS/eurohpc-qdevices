"""The path through Qrisp: each gate as a unitary, the order of a key, and what it calls. All of it needs Qrisp."""

import hashlib
import sys
import threading
from pathlib import Path

import pytest
from test_scan import BANNED

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from circuit import circuit_of  # noqa: E402
from gates import ONE, TWO, one_qubit  # noqa: E402
from overview import example_folders  # noqa: E402

ANGLES = {"rx": (0.7,), "ry": (0.7,), "rz": (0.7,), "u3": (0.7, 0.3, 1.1), "r": (0.7, 0.3), "crz": (0.7,),
          "rxx": (0.7,)}


def qrisp_module():
    """The new module, when Qrisp is here."""
    pytest.importorskip("qrisp")
    import qrisp_emulator

    return qrisp_emulator


def test_every_gate_of_ours_has_a_way_into_qrisp():
    emulator = qrisp_module()
    known = set(emulator.SAME_NAME) | set(emulator.OTHER_NAME) | set(emulator.BUILT_FROM_OTHERS)
    assert known == set(ONE) | set(TWO)


def our_unitary(name: str, size: int):
    """Our gate as a matrix: qubit 0 is the lowest bit of an index, and columns are what each basis state becomes."""
    np = pytest.importorskip("numpy")
    args = ANGLES.get(name, ())
    out = np.zeros((2 ** size, 2 ** size), dtype=complex)
    for i in range(2 ** size):
        state = one_qubit({i: 1 + 0j}, ONE[name](*args), 1) if size == 1 else TWO[name]({i: 1 + 0j}, 1, 2, *args)
        for j, amplitude in state.items():
            out[j, i] = amplitude
    return out


@pytest.mark.parametrize(("name", "size"), [*((name, 1) for name in ONE), *((name, 2) for name in TWO)])
def test_each_gate_in_qrisp_equals_ours_as_a_unitary_up_to_a_global_phase(name, size):
    emulator = qrisp_module()
    np = pytest.importorskip("numpy")
    qc = emulator.QuantumCircuit(size)
    emulator.add_gate(qc, name, (0, 1)[:size], ANGLES.get(name, ()))
    theirs, ours = qc.get_unitary(), our_unitary(name, size)
    if size == 2:                                # Qrisp's matrix holds qubit 0 as its highest bit
        swap = [0, 2, 1, 3]
        theirs = theirs[swap][:, swap]
    overlap = np.trace(ours.conj().T @ theirs) / 2 ** size
    assert abs(overlap) == pytest.approx(1, abs=1e-6)
    assert np.abs(theirs - overlap * ours).max() < 1e-6


def test_a_register_of_25_qubits_runs_with_its_keys_in_our_order():
    emulator = qrisp_module()
    assert emulator.qrisp_circuit(circuit_of(EXAMPLES / "vlq-ghz" / "GHZ.qasm")).num_qubits() == 25
    hello = circuit_of(EXAMPLES / "qrisp" / "hello" / "HELLO.qasm")
    assert emulator.qrisp_shares(hello) == hello.shares()


def test_qrisp_reads_the_highest_classical_bit_first_and_ignores_a_qubit_not_measured():
    emulator = qrisp_module()
    qc = emulator.QuantumCircuit(3, 2)
    qc.x(0)
    qc.x(2)
    qc.measure(0, 0)
    qc.measure(1, 1)
    assert dict(qc.run()) == {"01": 1.0}


class CalledModules:
    """Each module with a function called while it is on, in every thread."""

    def __init__(self) -> None:
        self.names: set = set()

    def _note(self, frame, event, arg) -> None:
        self.names.add(frame.f_globals.get("__name__", ""))
        if event == "c_call":
            self.names.add(getattr(arg, "__module__", None) or "")

    def __enter__(self):
        threading.setprofile(self._note)
        sys.setprofile(self._note)
        return self

    def __exit__(self, *_) -> None:
        sys.setprofile(None)
        threading.setprofile(None)

    def heads(self) -> set:
        """The digests of the first five characters of each module."""
        return {hashlib.sha256(name[:5].lower().encode("utf-8")).hexdigest() for name in self.names}


def test_the_path_through_qrisp_calls_nothing_on_the_scan_list():
    """Importing Qrisp loads more than it runs; here nothing on the scan's list runs."""
    emulator = qrisp_module()
    with CalledModules() as called:
        for folder in example_folders(EXAMPLES):
            emulator.folder_shares(folder)
    assert hashlib.sha256(b"qrisp").hexdigest() in called.heads()          # the watch does see what runs
    assert not called.heads() & {head for head, _, _ in BANNED}


def test_qrisp_s_own_r_is_our_r_a_quarter_turn_back():
    emulator = qrisp_module()
    np = pytest.importorskip("numpy")
    qc = emulator.QuantumCircuit(1)
    qc.r(0.7, 0.3, 0)
    theirs, ours = qc.get_unitary(), np.array(ONE["r"](0.7, 0.3 - np.pi / 2)).reshape(2, 2)
    assert abs(np.trace(ours.conj().T @ theirs) / 2) == pytest.approx(1, abs=1e-6)
