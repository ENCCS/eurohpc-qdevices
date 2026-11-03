"""The Qrisp examples: the writer, its files and each site's offline check; only the last test needs Qrisp."""

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as Space

import pytest
from fakes import places_in

from qdevices import config, dryrun
from qdevices.qasm import Qasm
from qdevices.sites import SITES

QRISP = Path(__file__).resolve().parent.parent / "examples" / "qrisp"
sys.path.insert(0, str(QRISP))
from qasm2 import ExportError, to_qasm2  # noqa: E402

sys.path.insert(0, str(QRISP.parent / "tools"))
from example_folder import KEPT  # noqa: E402

MANIFESTS = sorted(QRISP.glob("*/manifest.json"))
QUBITS = {"bell": 2, "ghz3": 3, "qft3": 3, "abstract_parameter": 3, "qaoa_maxcut": 5, "tutorial_qpe": 5, "qubo": 6,
          "constrained_mixer": 4, "qite1": 7, "ising": 6, "shor13": 6, "bv4": 5, "add_const": 3, "grover3": 3,
          "hello": 25, "ising2": 2}
QELIB1 = {"u3", "u2", "u1", "cx", "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "rx", "ry", "rz", "cz", "cy",
          "ch", "ccx", "crz", "cu1", "cu3", "measure", "barrier", "reset"}


def bit(name):
    return Space(identifier=name)


def circuit(*instructions, qubits=2, clbits=2):
    return Space(qubits=[bit(f"q{i}") for i in range(qubits)], clbits=[bit(f"c{i}") for i in range(clbits)],
                 data=[Space(op=Space(name=n, params=list(a)), qubits=[bit(f"q{i}") for i in qs],
                          clbits=[bit(f"c{i}") for i in cs]) for n, a, qs, cs in instructions])


def texts():
    return [(m.parent.name, f.read_bytes()) for m in MANIFESTS for f in m.parent.glob("*.qasm")]


def test_the_writer_writes_qelib1_gates_and_measures_in_order():
    qc = circuit(("h", [], [0], []), ("p", [0.5], [1], []), ("gphase", [0.3], [0], []), ("cx", [], [0, 1], []),
                 ("measure", [], [0], [0]), ("measure", [], [1], [1]))
    assert to_qasm2(qc) == ('OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nh q[0];\n'
                            "rz(0.5) q[1];\ncx q[0],q[1];\nmeasure q[0] -> c[0];\nmeasure q[1] -> c[1];\n")


def test_the_writer_writes_sx_as_rx_of_a_quarter_turn():
    qc = circuit(("sx", [], [0], []), ("sx_dg", [], [1], []), clbits=0)
    assert to_qasm2(qc).endswith("rx(1.5707963267948966) q[0];\nrx(-1.5707963267948966) q[1];\n")


@pytest.mark.parametrize("instruction", [("swap", [], [0, 1], []), ("rx", ["theta"], [0], []), ("rx", [], [0], [])],
                         ids=["gate-not-broken-down", "unbound-angle", "angles-missing"])
def test_the_writer_refuses_what_it_does_not_write(instruction):
    with pytest.raises(ExportError):
        to_qasm2(circuit(instruction))


def test_there_is_a_folder_for_each_qrisp_example():
    assert {m.parent.name for m in MANIFESTS} == set(QUBITS)


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda p: p.parent.name)
def test_each_qrisp_example_passes_the_euroqexa_dry_run(tmp_path, manifest):
    conf = config.load(QRISP.parent / "qdevices.toml")
    out = []
    assert dryrun.dry_run(manifest, cfg=conf, places=places_in(tmp_path), say=out.append) == 0, out


@pytest.mark.parametrize("name,text", texts(), ids=lambda v: v if isinstance(v, str) else "")
def test_each_text_uses_only_qelib1_gates(name, text):
    parsed = Qasm.parse(text.decode())
    assert parsed.gate_names <= QELIB1
    assert parsed.qubits == QUBITS[name]


@pytest.mark.parametrize("name,text", texts(), ids=lambda v: v if isinstance(v, str) else "")
def test_vlq_and_piastq_refuse_the_texts_offline(name, text):
    job = {"text": text, "options": {}}
    vlq = SITES["vlq"].validate(job, None)
    assert any("not an OpenQASM 3 text" in p for p in vlq) and any("not native on VLQ" in p for p in vlq)
    assert any("not an operation list of the broker" in p for p in SITES["piastq"].validate(job, None))


def test_qrisp_makes_the_same_files_again_and_each_ideal_names_the_likeliest_outcome(tmp_path):
    pytest.importorskip("qrisp")
    from programs import PROGRAMS
    from qrisp import QuantumCircuit

    # A process of its own: the writer sets NumPy's CPU features before NumPy is imported.
    subprocess.run([sys.executable, QRISP / "write_manifests.py", "--out", tmp_path], check=True, capture_output=True)
    for manifest in MANIFESTS:
        for file in (f for f in manifest.parent.iterdir() if f.name not in KEPT):
            assert (tmp_path / manifest.parent.name / file.name).read_bytes() == file.read_bytes(), file.name
    for program in PROGRAMS:
        made = program.build()
        if isinstance(made, QuantumCircuit):
            made.measure(made.qubits)
            res = made.run(shots=1000)
        else:
            res = made.get_measurement()
        assert str(max(res, key=res.get)) in program.ideal, program.name
