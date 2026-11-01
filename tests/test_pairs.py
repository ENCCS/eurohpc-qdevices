"""The operand reader of qdevices.qasm, and the pairs of a no_modify text against the cz loci of a read."""

import json

from fakes import FakeClock, cfg, places_in
from fakes.eqe import Portal, manifest, posts, send

from qdevices import dryrun
from qdevices.qasm import Qasm
from qdevices.sites.euroqexa import EuroQExa

PAIRS = [(0, 1), (1, 2)]
READ = {"read_at": "2026-01-05T11:00:00+00:00", "machine": "M1", "qubits": 3, "gate_names": ["cz", "r"],
        "instructions": [["r", {}], ["cz", {"(0, 1)": None, "(1, 2)": None}]]}
OPENQASM_3 = ('OPENQASM 3.0;\ninclude "stdgates.inc";\ngate r(theta, phi) q {\n    gphase(0);\n}\n// a comment\n'
              "qubit[25] q;\nbit[2] c;\nr(pi/2, -pi/2) q[1];\nprx(0.5, 0.25) q[0];\nmove q[0], q[24];\n"
              "cz q[1], q[24];\nc[0] = measure q[0];\nmeasure q[1] -> c[1];\n")
NOT_MADE = "the pair check was not made: "


def cz(a: int, b: int) -> bytes:
    return (f'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\ncreg c[3];\nr(0.5, 0.25) q[0];\n'
            f"cz q[{a}],q[{b}];\nmeasure q -> c;\n").encode()


def job(text: bytes, no_modify: bool = True) -> dict:
    return {"text": text, "shots": 10, "options": {"no_modify": True} if no_modify else {}}


def test_the_operand_reader_gives_each_operation_with_its_qubit_indices():
    parsed = Qasm.parse(OPENQASM_3)
    assert parsed.register == ("q", 25)
    assert parsed.operations == [("r", [1]), ("prx", [0]), ("move", [0, 24]), ("cz", [1, 24]),
                                 ("measure", [0]), ("measure", [1])]
    assert Qasm.parse(cz(1, 0).decode()).operations == [("r", [0]), ("cz", [1, 0]), ("measure", [0]), ("measure", [1]),
                                                         ("measure", [2])]
    assert Qasm.parse("OPENQASM 2.0;\nqreg a[1];\nqreg b[1];\ncz a[0],b[0];\n").operations is None
    assert Qasm.parse("OPENQASM 3.0;\nqubit[2] q;\nfor int i in [0:1] { x q[i]; }\n").operations is None


def test_with_no_modify_a_pair_not_listed_fails_and_a_reversed_pair_is_a_note():
    assert EuroQExa.validate(job(cz(0, 2)), READ) == [
        "cz on qubits 0 and 2: the read lists no cz locus (0, 2) or (2, 0)"]
    assert EuroQExa.validate(job(cz(1, 0)), READ) == []
    assert EuroQExa.notes(job(cz(1, 0)), READ) == ["cz on qubits 1 and 0: the read lists the pair as (0, 1)"]
    assert EuroQExa.validate(job(cz(0, 1)), READ) == [] and EuroQExa.notes(job(cz(0, 1)), READ) == []
    assert EuroQExa.validate(job(cz(0, 2), no_modify=False), READ) == []
    assert EuroQExa.notes(job(cz(0, 2), no_modify=False), READ) == []


def test_the_pair_check_says_when_it_was_not_made():
    two = b'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg a[2];\nqreg b[1];\ncz a[0],a[1];\n'
    assert EuroQExa.validate(job(two), READ) == []
    assert EuroQExa.notes(job(two), READ) == [NOT_MADE + "it reads only a text with one quantum register, in plain "
                                              "statements"]
    unread = {**READ, "instructions": [["cz", {"0-1": None}]]}
    assert EuroQExa.validate(job(cz(0, 2)), unread) == []
    assert EuroQExa.notes(job(cz(0, 2)), unread) == [NOT_MADE + "the cz loci of the read cannot be read"]


def test_a_pair_not_listed_fails_the_dry_run_and_stops_the_live_call_before_any_job(tmp_path):
    places, out, seen = places_in(tmp_path), [], []
    (places.reads / "euroqexa").mkdir(parents=True)
    (places.reads / "euroqexa" / "read_20260105T110000Z.json").write_text(json.dumps(READ))
    path = manifest(tmp_path / "m", cz(0, 2), no_modify=True)
    assert dryrun.dry_run(path, cfg=cfg(), places=places, clock=FakeClock(), say=out.append) == 1
    assert "  FAILED: order 1 (J1): cz on qubits 0 and 2: the read lists no cz locus (0, 2) or (2, 0)" in out
    code, lines = send(path, Portal(3, PAIRS, seen), places, FakeClock(), max_order=1)
    assert code == 1 and lines[-1]["kind"] == "check" and not posts(seen)


def test_a_reversed_pair_is_a_note_in_the_read_line_and_the_job_goes(tmp_path):
    seen = []
    code, lines = send(manifest(tmp_path / "m", cz(1, 0), no_modify=True), Portal(3, PAIRS, seen),
                       places_in(tmp_path), FakeClock(), max_order=1)
    read = next(e for e in lines if e["event"] == "read")
    assert code == 0 and len(posts(seen)) == 1
    assert read["notes"] == ["order 1 (J1): cz on qubits 1 and 0: the read lists the pair as (0, 1)"]
