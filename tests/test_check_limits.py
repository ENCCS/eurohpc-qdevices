"""Huge numbers and deep nesting are refused or left unread by the check."""

import json

import pytest
from fakes import QASM, cfg, lines_of, places_in, records_of, write_manifest
from fakes.vlq import creates, go, make_vlq

from qdevices.dryrun import dry_run
from qdevices.manifest import ManifestError
from qdevices.qasm import Qasm
from qdevices.sites import SITES

HUGE = "9" * 5000                     # more digits than Python turns into an int
TOO_LARGE = "the file names a register or an index of more than 5 digits, more than any machine has"
HEAD2 = 'OPENQASM 2.0;\ninclude "qelib1.inc";\n'
VLQ_HEAD = 'OPENQASM 3.0;\ngate r(theta, phi) q {\n    gphase(0);\n}\n'
READ = {"machine": "M1", "qubits": 5, "gate_names": ["cz", "measure", "prx"],
        "instructions": {"cz": {"(0, 1)": {}}, "prx": {}}}


def problems(site: str, text: str, read=None, **options) -> list[str]:
    return SITES[site].validate({"text": text.encode(), "shots": 10, "options": options}, read)


def dry(tmp_path, site: str, text: str, shots: int = 10) -> tuple[int, list[str]]:
    m = write_manifest(tmp_path / "m", site=site, jobs=(("J1", shots),), text=text.encode())
    said: list[str] = []
    return dry_run(m, cfg=cfg(), places=places_in(tmp_path), say=said.append), said


@pytest.mark.parametrize("text", [
    f"{HEAD2}qreg q[{HUGE}];\ncreg c[1];\nx q[0];\nmeasure q[0] -> c[0];\n",           # a register
    f"{HEAD2}qreg q[2];\ncreg c[1];\nx q[{HUGE}];\nmeasure q[0] -> c[0];\n",           # an index
    f"{HEAD2}qreg q[2];\ncreg c[1];\nx q[{'0' * 5000}1];\nmeasure q[0] -> c[0];\n",     # leading zeros count
])
def test_a_number_of_more_digits_than_python_converts_is_refused_by_the_dry_run(tmp_path, text):
    assert problems("euroqexa", text) == [TOO_LARGE]
    code, said = dry(tmp_path, "euroqexa", text)
    assert code == 1 and f"  FAILED: order 1 (J1): {TOO_LARGE}" in said


def test_a_register_far_above_any_machine_is_not_read_so_the_pair_check_cannot_exhaust_the_memory():
    text = f"{HEAD2}qreg q[1000000000];\ncreg c[1];\nprx(0.5, 0) q;\ncz q[0], q[1];\nmeasure q[0] -> c[0];\n"
    parsed = Qasm.parse(text)
    assert parsed.too_large and parsed.operations is None and parsed.gate_count is None
    assert problems("euroqexa", text, READ, no_modify=True) == [TOO_LARGE]
    assert Qasm.parse(text.replace("1000000000", "99999")).too_large is False         # five digits are read


def test_a_vlq_index_of_more_digits_than_python_converts_stops_at_the_check_before_the_init_job(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path)
    text = f"{VLQ_HEAD}qubit[2] q;\nbit[1] c;\nr(0.5, 0) q[{HUGE}];\nc[0] = measure q[0];\n".encode()
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("V1", 10),), text=text)
    assert go(m, site, places, clock, max_order=1) == 1
    stop = lines_of(records_of(places)[0])[-1]
    assert (stop["event"], stop["kind"], stop["problems"]) == ("stop", "check", [f"order 1 (V1): {TOO_LARGE}"])
    assert creates(fake) == []                                  # no init job, no node time


def test_shots_above_a_billion_are_refused_by_the_manifest_before_any_job(tmp_path):
    places, clock, fake, m, site = make_vlq(tmp_path)
    man = json.loads(m.read_text())
    man["jobs"] = [{**man["jobs"][0], "shots": 10 ** 400}]
    m.write_text(json.dumps(man))
    with pytest.raises(ManifestError, match="job 1: shots must be at most 1,000,000,000"):
        go(m, site, places, clock, max_order=1)
    assert creates(fake) == [] and records_of(places) == []    # ManifestError: REFUSED at the command line
    code, said = dry(tmp_path / "d", "vlq", QASM.decode(), shots=10 ** 9 + 1)
    assert code == 1 and "  FAILED: job 1: shots must be at most 1,000,000,000" in said


def nested(depth: int) -> str:
    return f"{HEAD2}qreg q[1];\ncreg c[1];\n" + "if (c == 1) " * depth + "x q[0];\nmeasure q[0] -> c[0];\n"


@pytest.mark.parametrize("depth", [33, 990, 5000])
def test_if_nested_deeper_than_the_limit_is_not_read_and_gives_no_recursion_error(tmp_path, depth):
    parsed = Qasm.parse(nested(depth))
    assert parsed.operations is None and parsed.gate_count is None
    code, said = dry(tmp_path, "euroqexa", nested(depth))
    assert code == 0 and "gates not counted" in said[-6]


def test_if_nested_to_the_limit_is_read_as_before():
    assert Qasm.parse(nested(32)).operations == [("x", [0]), ("measure", [0])]
    assert Qasm.parse(nested(32)).gate_count == 2
