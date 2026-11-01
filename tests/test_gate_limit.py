"""The limit of shots times gates of a Euro-Q-Exa job (LRZ): the count of a text, the dry run, the generic rule."""

from fakes import QASM, FakeClock, FakeSite, cfg, events, places_in, records_of, send, write_manifest
from fakes.eqe import Portal, manifest, posts
from fakes.eqe import send as send_eqe

from qdevices import dryrun, rules
from qdevices.qasm import DEPTH, Qasm
from qdevices.sites import SITES, euroqexa
from qdevices.sites.base import Site

HEAD = 'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[3];\ncreg c[3];\n'
BELL = "gate bell a, b { h a; cx a, b; }\n"
LIMIT = euroqexa.EuroQExa.max_shots_times_gates
COMPILED = "without no_modify the site compiles the circuit, so its own count of gates can be higher"
UNCOUNTED = b"OPENQASM 3.0;\nqubit[1] q;\nbit[1] c;\nfor int i in [0:1] { x q[0]; }\nc[0] = measure q[0];\n"


def count(body: str) -> int | None:
    """The count of a text of three qubits, q[0] to q[2], with these statements."""
    return Qasm.parse(HEAD + body).gate_count


def dry(path, tmp_path) -> tuple[int, list[str]]:
    out = []
    code = dryrun.dry_run(path, cfg=cfg(), places=places_in(tmp_path), clock=FakeClock(), say=out.append)
    return code, out


def test_each_gate_measure_and_reset_counts_once_and_barrier_and_declarations_do_not():
    assert count("") == 0
    assert count("h q[0];\ncx q[0],q[1];\nrz(pi/4) q[2];\nU(0, 0, 0) q[1];\n") == 4
    assert count("measure q[0] -> c[0];\nreset q[1];\nbarrier q[0],q[1];\nbarrier q;\n") == 2
    assert count("// h q[0];\n/* x q[1]; */\nx q[2];\n") == 1
    assert Qasm.parse(QASM.decode()).gate_count == 2                  # x q[0]; measure q -> c; on one qubit


def test_a_statement_on_a_whole_register_counts_once_for_each_qubit():
    assert count("h q;\n") == 3 and count("measure q -> c;\n") == 3 and count("reset q;\n") == 3
    assert count("qreg r[5];\ncx q[0],r;\n") == 5
    assert count("barrier q;\n") == 0


def test_a_call_of_a_gate_the_text_defines_counts_its_body_expanded():
    twice = BELL + "gate twice a, b { bell a, b; barrier a, b; bell b, a; }\n"
    assert count(BELL + "bell q[0],q[1];\n") == 2
    assert count(twice + "twice q[0],q[1];\n") == 4
    assert count(BELL + "qreg r[3];\nbell q, r;\n") == 6                 # whole registers: three calls of two
    assert count("opaque magic a;\nmagic q[0];\n") == 1                 # no body in the text: one operation


def test_a_statement_under_if_counts():
    assert count("if (c == 1) x q[0];\n") == 1
    assert count("if (c == 5) measure q -> c;\n") == 3
    assert count(BELL + "if (c == 1) bell q[0],q[1];\n") == 2


def test_the_statements_of_openqasm_3_and_a_qubit_declared_with_no_size():
    text = ('OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[2] q;\nqubit a;\nbit[2] c;\nbit b;\nh q;\nx a;\n'
            "c = measure q;\nb = measure a;\nc[0] = measure q[0];\n")
    assert Qasm.parse(text).gate_count == 2 + 1 + 2 + 1 + 1


def test_a_text_it_cannot_read_has_no_count():
    assert Qasm.parse(UNCOUNTED.decode()).gate_count is None            # a block in braces
    assert count("ctrl @ x q[0], q[1];\n") is None
    assert count("x q[0:2];\n") is None
    assert count("gate loop a { loop a; }\nloop q[0];\n") is None       # a gate that calls itself


def test_a_statement_on_a_whole_register_whose_size_is_not_a_number_has_no_count():
    text = "OPENQASM 3.0;\nconst uint n = 4;\nqubit[n] q;\nbit[n] c;\n"
    assert Qasm.parse(text + "h q[0];\nc[0] = measure q[0];\n").gate_count == 2
    assert Qasm.parse(text + "h q;\nc = measure q;\n").gate_count is None   # not 2: each statement acts on 4 qubits


def test_the_calls_of_defined_gates_are_followed_to_the_depth_cap_and_each_body_is_counted_once():
    wide = "gate g0 a { x a; }\n" + "".join(f"gate g{i} a {{ g{i - 1} a; g{i - 1} a; }}\n" for i in range(1, 31))
    assert count(wide + "g30 q[0];\n") == 2 ** 30
    deep = "gate d0 a { x a; }\n" + "".join(f"gate d{i} a {{ d{i - 1} a; }}\n" for i in range(1, DEPTH + 1))
    assert count(deep + f"d{DEPTH - 1} q[0];\n") == 1
    assert count(deep + f"d{DEPTH} q[0];\n") is None


def test_euroqexa_holds_the_limit_and_the_other_sites_none():
    assert LIMIT == 3_000_000 and Site.max_shots_times_gates is None
    assert {name: cls.max_shots_times_gates for name, cls in SITES.items()} == {
        "euroqexa": 3_000_000, "vlq": None, "piastq": None}
    assert rules.gate_limit in rules.GENERIC["before_job"]


def test_the_rule_passes_a_job_at_the_limit_and_a_site_with_no_limit():
    state = {"max_shots_times_gates": LIMIT, "gate_count": 3}
    at, above = rules.gate_limit({"shots": LIMIT // 3}, state), rules.gate_limit({"shots": LIMIT // 3 + 1}, state)
    assert at["passed"] and at["shots_times_gates"] == LIMIT
    assert not above["passed"] and above["reason"] == (
        "1,000,001 shots times 3 gates is 3,000,003, above the 3,000,000 shots times gates a job may hold (LRZ)")
    assert rules.gate_limit({"shots": 10 ** 9}, {"max_shots_times_gates": None, "gate_count": 3})["passed"]
    uncounted = rules.gate_limit({"shots": 10 ** 9}, {**state, "gate_count": None})
    assert uncounted["passed"] and "cannot be counted" in uncounted["note"] and "(LRZ)" in uncounted["note"]


def test_the_dry_run_shows_shots_times_gates_and_fails_a_job_above_the_limit(tmp_path):
    path = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", LIMIT // 2 + 1)))     # two gates each
    code, out = dry(path, tmp_path)
    plan = [line for line in out if line.startswith("    [")]
    assert code == 1 and out[-1] == "Dry run FAILED. Nothing was sent."
    assert "  2 gates, 20 shots times gates" in plan[0] and plan[0].endswith("  ok")
    assert "  2 gates, 3,000,002 shots times gates" in plan[1] and not plan[1].endswith("  ok")
    assert ("  FAILED: order 2 (J2): 1,500,001 shots times 2 gates is 3,000,002, above the 3,000,000 shots times "
            "gates a job may hold (LRZ)") in out
    path = write_manifest(tmp_path / "at", jobs=(("J1", LIMIT // 2),))
    assert dry(path, tmp_path)[0] == 0


def test_the_dry_run_notes_a_circuit_the_site_compiles_and_a_text_it_cannot_count(tmp_path):
    for no_modify, notes in ((False, 1), (True, 0)):
        code, out = dry(manifest(tmp_path / str(no_modify), QASM, no_modify=no_modify), tmp_path)
        assert code == 0 and out.count(f"  note      order 1 (J1): {COMPILED}") == notes
    code, out = dry(manifest(tmp_path / "loop", UNCOUNTED), tmp_path)
    assert code == 0 and any(line.endswith("options {}  gates not counted  ok") for line in out)
    assert any(line.startswith("  note      order 1 (J1): the gate operations of the text cannot be counted")
               for line in out)


def test_the_rule_stops_the_call_before_a_job_above_the_limit_with_no_job_request(tmp_path, places, clock):
    seen = []
    path = write_manifest(tmp_path / "m", jobs=(("J1", LIMIT // 2 + 1),))
    code, lines = send_eqe(path, Portal(5, [], seen), places, clock, max_order=1)
    stop = lines[-1]
    assert code == 2 and stop["event"] == "stop" and stop["kind"] == "rule" and stop["rule"] == "shots_times_gates"
    assert not posts(seen) and not [e for e in lines if e["event"] == "submitting"]
    rule = next(e for e in lines if e["event"] == "rule" and e["rule"] == "shots_times_gates")
    assert rule["passed"] is False and rule["gate_count"] == 2 and rule["limit"] == LIMIT
    assert rule["reason"].endswith("above the 3,000,000 shots times gates a job may hold (LRZ)")


def test_a_job_at_the_limit_goes_and_a_later_job_above_it_is_not_sent(tmp_path, places, clock):
    path = write_manifest(tmp_path / "m", jobs=(("J1", LIMIT // 2), ("J2", LIMIT // 2 + 1)))
    site = FakeSite()
    site.max_shots_times_gates = LIMIT
    assert send(path, site, places, clock, max_order=2) == 2
    assert [c for c in site.calls if c[0] in ("prepare", "submit")] == [("prepare", 1), ("submit", 1)]
    rec = records_of(places)[0]
    assert [e["order"] for e in events(rec, "result")] == [1]
    judged = [(e["order"], e["passed"]) for e in events(rec, "rule") if e["rule"] == "shots_times_gates"]
    assert judged == [(1, True), (2, False)]


def test_a_users_rule_reads_the_gate_count_and_the_limit_in_the_state_not_in_the_job(tmp_path, places, clock):
    seen = []

    def look(job, state):
        seen.append((state["gate_count"], state["max_shots_times_gates"], "gate_count" in job))
        return {"rule": "look", "passed": True}

    path = write_manifest(tmp_path / "m", jobs=(("J1", 10),))
    assert send(path, FakeSite(), places, clock, max_order=1, user_rules={"before_job": look}) == 0
    assert seen == [(2, None, False)]
