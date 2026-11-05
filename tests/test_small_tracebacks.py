"""Faults that ended in a traceback with nothing sent, each now a plain outcome."""

import json

import pytest
from fakes import TOKEN, FakeSite, cfg, lines_of, records_of, send, write_manifest

from qdevices import monitor, runner
from qdevices import record as records
from qdevices.ledger import Ledger
from qdevices.qasm import Qasm
from qdevices.qasm.statement import ENTRIES
from qdevices.resolve import resolve
from qdevices.sites import loci
from qdevices.sites.euroqexa import EuroQExa


def append(rec, text: str) -> None:
    with rec.open("a", encoding="utf-8") as fh:
        fh.write(text)


@pytest.mark.parametrize("orders", [5, "12", [[1]], {"1": 2}, [True, 1.5]])
def test_a_skip_line_whose_orders_are_of_the_wrong_type_names_no_order(tmp_path, places, clock, orders):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    append(rec, json.dumps({"event": "skip", "orders": orders}) + "\n")
    assert monitor.job_rows(lines_of(rec))[1:] == monitor.job_rows(lines_of(rec)[:-1])[1:]
    assert send(m, FakeSite(), places, clock, max_order=3, resume=rec) == 0


def test_a_machine_that_is_a_list_names_no_site():
    assert Ledger([{"event": "start", "machine": ["VLQ"]}]).site is None


def test_a_vlq_job_id_of_more_digits_than_int_reads_is_kept_as_text(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("J1", 10),))
    assert send(m, FakeSite("vlq", seconds_left=3600, submits={1: ("noanswer",)}), places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    long_id = "7" * 5000
    said = resolve(rec, 1, long_id, places=places, clock=clock, host="h")
    assert said == f"order 1 has the job {long_id}; a resume collects it"
    assert lines_of(rec)[-1]["id"] == long_id


def test_a_locus_of_more_digits_than_int_reads_cannot_be_read():
    assert loci._pair("(" + "1" * 5000 + ", 2)") is None


def test_a_failed_close_after_the_loop_returned_keeps_its_exit_code(tmp_path, places, clock, monkeypatch):
    site = FakeSite()

    def submit(job, note, prepared=None):
        raise RuntimeError("a fault")

    site.submit = submit
    monkeypatch.setattr(records.Record, "close", lambda self: (self._fh.close(), (_ for _ in ()).throw(OSError))[0])
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 3


def test_the_notes_of_the_opening_of_a_resume_go_through_the_token_filter(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    append(rec, f'{{"event": "submitted", "order": 2, "id": "{TOKEN}')
    said: list[str] = []
    assert runner.send(m, FakeSite(), cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="host-a",
                       say=said.append, resume=rec) == 0
    assert any("is cut" in text for text in said) and not any(TOKEN[:8] in text for text in said)


def test_the_entries_of_a_text_are_capped_before_a_register_is_expanded():
    text = "qreg q[99999];\n" + "h q;\n" * (ENTRIES // 99999 + 1)
    assert Qasm.parse(text).operations is None
    assert Qasm.parse("qreg q[99999];\nh q;\n").operations is not None


def test_a_text_over_the_cap_is_refused_and_not_sent_unchecked():
    text = "qreg q[99999];\n" + "h q;\n" * (ENTRIES // 99999 + 1)
    refusal = f"the text has more than {ENTRIES:,} operations, more than the checks read"
    assert Qasm.parse(text).qubit_problems(None) == [refusal]
    job = {"text": ("OPENQASM 2.0;\n" + text).encode(), "options": {"no_modify": True}}
    assert EuroQExa.validate(job, {"qubits": 99999, "instructions": []})


def test_no_pair_check_is_made_once_a_qubit_problem_is_found(monkeypatch):
    monkeypatch.setattr(loci, "pair_check", lambda *a: pytest.fail("a pair check was made"))
    job = {"text": b"OPENQASM 2.0;\nqreg q[99];\ncx q[0], q[1];\n", "options": {"no_modify": True}}
    read = {"qubits": 5, "instructions": [["cz", [[0, 1]]]]}
    assert EuroQExa.validate(job, read) == ["the text declares 99 qubits, the machine has 5"]
    assert EuroQExa.notes(job, read) == []
