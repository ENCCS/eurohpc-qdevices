"""The table of the day of VLQ in its init artefact, the check of a text against it, and the bounded walk."""

import base64
import hashlib
import json
import pickle
import time
from dataclasses import asdict

import httpx
import pytest
from fakes import FakeClock, lines_of, places_in, records_of, write_manifest
from fakes.vlq import TOKEN, Counts, FakeVLQ, creates, go

from qdevices.ledger import Ledger
from qdevices.sites import pickle_reader
from qdevices.sites.vlq import VLQ, table
from qdevices.sites.vlq.results import ResultsFile

RESONATOR = "resonator-1"
TEXT = (b'OPENQASM 3.0;\ninclude "stdgates.inc";\ngate r(theta, phi) q {\n    gphase(0);\n}\n'
        b"gate move q0, q1 {\n    gphase(0);\n}\nqubit[25] q;\nbit[2] c;\nr(pi/2, pi/2) q[0];\nmove q[0], q[24];\n"
        b"cz q[1], q[24];\nmove q[0], q[24];\nc[0] = measure q[0];\nc[1] = measure q[1];\n")


class Implementation:
    def __init__(self, loci):
        self.loci = loci


class Gate:
    def __init__(self, loci):
        self.implementations = {"default": Implementation(loci)}


class Architecture:
    """Its state keeps the fields under "__dict__", as some model classes keep theirs."""

    def __init__(self, qubits, resonators, gates):
        self.qubits, self.computational_resonators, self.gates = qubits, resonators, gates

    def __getstate__(self):
        return {"__dict__": dict(vars(self)), "__fields_set__": set(vars(self))}


def names(qubits: int) -> list[str]:
    return [f"qubit-{i:02d}" for i in range(1, qubits + 1)]


def index(qubits: int) -> dict:
    """The qubits at 0 to qubits - 1, and the resonator after them."""
    return {**{name: i for i, name in enumerate(names(qubits))}, RESONATOR: qubits}


def artefact(qubits: int) -> bytes:
    """A synthetic iqm_target_attrs.pkl: the qubits round one resonator, the resonator at index `qubits`."""
    loci = tuple((name, RESONATOR) for name in names(qubits))
    gates = {"cz": Gate(loci), "move": Gate(loci), "prx": Gate(tuple((name,) for name in names(qubits)))}
    return pickle.dumps({"iqm_component_to_idx": index(qubits), "iqm_include_resonators": False,
                         "iqm_dqa": Architecture(names(qubits), [RESONATOR], gates)})


def digest(qubits: int) -> str:
    """The SHA-256 of that table as the manual gives it: compact JSON, sorted keys, each list sorted."""
    pairs = sorted([name, RESONATOR] for name in names(qubits))
    text = json.dumps({"index": index(qubits), "qubits": names(qubits), "resonators": [RESONATOR],
                       "loci": {"cz": pairs, "move": pairs}}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TableVLQ(FakeVLQ):
    """The fake service, with `attrs` as the init artefact iqm_target_attrs.pkl."""

    def __init__(self, places, attrs: bytes):
        super().__init__(places)
        self.attrs = attrs

    def __call__(self, request: httpx.Request) -> httpx.Response:
        answer = super().__call__(request)
        if request.url.path.endswith("DownloadFileFromCluster") and b"/iqm_target_attrs.pkl" in request.content:
            return httpx.Response(200, json=base64.b64encode(self.attrs).decode())
        return answer


def make(tmp_path, attrs: bytes):
    """(places, clock, fake service, manifest of one job with TEXT, VLQ site over the fake service)."""
    places, clock = places_in(tmp_path), FakeClock()
    fake = TableVLQ(places, attrs)
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("V1", 10),), text=TEXT)
    site = VLQ(TOKEN, "VLQ", lexis_project="TEST-LEXIS", resource="R1", clock=clock, sleep=clock.sleep,
               wait_seconds=60, transport=httpx.MockTransport(fake))
    return places, clock, fake, m, site


def dones(lines: list[dict]) -> list[dict]:
    return [e for e in lines if e["event"] == "init" and e["step"] == "init_done"]


def test_a_text_that_does_not_fit_the_table_stops_before_the_metered_job_and_a_resume_tries_again(tmp_path):
    places, clock, fake, m, site = make(tmp_path, artefact(23))          # the resonator at 23; the text uses 24
    assert go(m, site, places, clock, max_order=1) == 1
    rec = records_of(places)[0]
    lines = lines_of(rec)
    assert dones(lines)[0]["table"]["size"] == 24 and dones(lines)[0]["table"]["resonators"] == [23]
    assert dones(lines)[0]["table_problems"] == [
        "move on indices 0 and 24: the table of the day has no index 24 (its size is 24)",
        "cz on indices 1 and 24: the table of the day has no index 24 (its size is 24)"]
    assert lines[-1]["event"] == "stop" and lines[-1]["kind"] == "prepare" and lines[-1]["step"] == "table"
    assert len(creates(fake)) == 1 and ("create", "backend_run") not in fake.last_line_at    # no metered job
    assert Ledger(lines).orders[1].status == "unsent"
    fake.attrs = artefact(24)                                             # a later table: the resonator at 24
    assert go(m, site, places, clock, resume=rec, max_order=1) == 0
    lines = lines_of(rec)
    assert len(creates(fake)) == 3 and len(dones(lines)) == 2              # a new init job, then the metered job
    assert dones(lines)[1]["table"] == {"size": 25, "resonators": [24], "sha256": digest(24)}
    assert [e for e in lines if e["event"] == "result"]


def test_a_text_that_fits_the_table_goes_and_init_done_holds_the_digest_of_the_table(tmp_path):
    places, clock, fake, m, site = make(tmp_path, artefact(24))
    assert go(m, site, places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    done = dones(lines_of(rec))[0]
    assert done["table"] == {"size": 25, "resonators": [24], "sha256": digest(24)}
    assert "table_note" not in done and "table_problems" not in done
    assert ("create", "backend_run") in fake.last_line_at
    text = rec.read_text()
    assert "qubit-" not in text and RESONATOR not in text                 # no name of a component is written


def test_a_table_that_cannot_be_read_gives_a_note_and_the_job_goes(tmp_path):
    places, clock, _fake, m, site = make(tmp_path, b"not a pickle")
    assert go(m, site, places, clock, max_order=1) == 0
    lines = lines_of(records_of(places)[0])
    done = dones(lines)[0]
    assert "table" not in done and "table_problems" not in done
    assert done["table_note"].startswith("the table of the day was not read (the pickle cannot be read")
    assert [e for e in lines if e["event"] == "result"]


def test_the_reader_takes_the_table_in_its_form_and_no_other(monkeypatch):
    assert table.Table.parse(artefact(24)).fields == {"size": 25, "resonators": [24], "sha256": digest(24)}
    for data in (b"not a pickle", pickle.dumps([1, 2]), pickle.dumps({"iqm_component_to_idx": {"a": 0}})):
        with pytest.raises(pickle_reader.PickleRefused):
            table.Table.parse(data)
    monkeypatch.setattr(table, "WIDTH", 10)
    with pytest.raises(pickle_reader.PickleRefused, match="more than 10 entries"):
        table.Table.parse(artefact(24))


def test_the_check_gives_each_problem_once():
    day = table.Table.of(index={"a": 0, "b": 1, "c": 2, "r": 3}, qubits=frozenset({"a", "b", "c"}),
                         resonators=frozenset({"r"}),
                         loci={"cz": frozenset({("a", "r"), ("b", "r")}), "move": frozenset({("a", "r")})})
    text = ("OPENQASM 3.0;\nqubit[5] q;\nbit[1] c;\nr(pi, 0) q[3];\ncz q[1], q[2];\ncz q[3], q[0];\n"
            "move q[1], q[3];\ncz q[2], q[3];\nprx(0.5, 0) q[4];\ncz q[0], q[3];\nc[0] = measure q[0];\n"
            "cz q[1], q[2];\n")
    assert day.problems(text) == [
        "r on index 3: index 3 is not a qubit in the table of the day",
        "cz on indices 1 and 2: the second index is not the resonator, which the table of the day has at 3",
        "cz on indices 3 and 0: the second index is not the resonator, which the table of the day has at 3",
        "move on indices 1 and 3: the table of the day lists no move locus for these indices",
        "cz on indices 2 and 3: the table of the day lists no cz locus for these indices",
        "prx on index 4: the table of the day has no index 4 (its size is 4)"]
    assert day.problems("OPENQASM 3.0;\nqubit[1] a;\nqubit[1] b;\ncz a[0], b[0];\n") is None


def test_a_pickle_of_shared_lists_is_walked_at_once():
    node = [1]
    for _ in range(8):
        node = [node] * 64                       # 64 references to one shared list, eight levels deep
    start = time.monotonic()
    assert asdict(ResultsFile.parse(pickle.dumps(node))) == dict.fromkeys(
        ("counts", "success", "shots", "calibration_set"))
    assert time.monotonic() - start < 5


def test_the_walk_caps_each_list_and_each_dict_and_the_parts_in_all():
    walk = pickle_reader.Walk(list_width=10, dict_width=12, nodes=25)
    assert len(walk.fields({str(i): i for i in range(20)})) == 12 and walk.cut
    walk = pickle_reader.Walk(list_width=10, dict_width=12, nodes=25)
    assert [len(walk.entries(list(range(10)))) for _ in range(3)] == [10, 10, 5] and walk.cut
    shared = []
    assert [walk.due(shared, depth) for depth in (5, 5, 6, 2, 0, 0)] == [True, False, False, True, True, False]


def test_a_results_file_gives_1024_fields_of_a_dict_and_64_entries_of_a_list():
    found = Counts({"1": 10})
    dicts = [{**{f"f{i}": i for i in range(n)}, "last": found} for n in (1023, 1024)]   # field 1024, then 1025
    lists = [[0] * n + [found] for n in (63, 64)]                                       # entry 64, then 65
    counts = [ResultsFile.parse(pickle.dumps(shape)).counts for shape in dicts + lists]
    assert counts == [{"1": 10}, None, {"1": 10}, None]


def test_a_shared_part_met_deep_first_is_searched_again_from_its_shallow_place():
    shared = [[Counts({"1": 10})]]               # the counts two levels below the shared part
    deep = shared
    for _ in range(7):
        deep = [deep]                            # first met at depth 8, where the counts are out of reach
    assert ResultsFile.parse(pickle.dumps([deep, shared])).counts == {"1": 10}
