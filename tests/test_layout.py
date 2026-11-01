"""The layout of a machine: its digest, the live check that stores it, and the pin of a manifest."""

import json

from fakes import QASM, TOKEN, FakeClock, cfg, events, places_in, records_of, write_manifest
from fakes import send as send_to
from fakes.eqe import Portal, manifest, posts, send, site
from fakes.piastq import PAYLOAD, Broker

from qdevices import check, dryrun, layout
from qdevices.layout import Layout, Pin

OLD = [(i, i + 1) for i in range(5)] + [(0, 5), (1, 4)]      # 6 qubits, 7 pairs
NEW = [(i, i + 1) for i in range(4)] + [(0, 4)]              # 5 qubits, 5 pairs


def test_the_canonical_text_sorts_each_pair_and_the_list():
    assert Layout.of(3, [(2, 1), (1, 0)]).canonical == "qubits=3;pairs=0-1,1-2"
    assert Layout.of(3, [(0, 1), (1, 2)]).fields == Layout.of(3, [(2, 1), (1, 0), (0, 1)]).fields
    assert Layout.of(3, [(0, 1)]).fields["layout_sha256"] != Layout.of(4, [(0, 1)]).fields["layout_sha256"]
    assert Layout.of(6, OLD).fields["pairs"] == 7 and Layout.of(5, NEW).fields["pairs"] == 5


def test_check_live_prints_and_stores_the_layout_and_the_line_to_pin_it(tmp_path):
    places, clock, out = places_in(tmp_path), FakeClock(), []
    eqe = site(Portal(5, NEW, []))
    assert check.check("euroqexa", live=True, token=TOKEN, manifest_path=manifest(tmp_path / "m", QASM), cfg=cfg(),
                       places=places, clock=clock, sleep=clock.sleep, host="h", make_site=lambda *a, **k: eqe,
                       say=out.append) == 0
    stored = json.loads(next((places.reads / "euroqexa").glob("read_*.json")).read_text())
    pin = Layout.of(5, NEW).fields
    assert {key: stored[key] for key in layout.KEYS} == pin
    assert f"  layout_sha256: {pin['layout_sha256']}" in out and "  pairs: 5" in out
    assert any(line.endswith('"layout": ' + json.dumps(pin)) for line in out)


def test_a_layout_other_than_the_pin_stops_before_the_first_job(tmp_path):
    seen = []
    path = manifest(tmp_path / "m", QASM, layout=Layout.of(6, OLD).fields)
    code, lines = send(path, Portal(5, NEW, seen), places_in(tmp_path), FakeClock(), max_order=1)
    stop = lines[-1]
    assert code == 1 and stop["event"] == "stop" and stop["kind"] == "check" and not posts(seen)
    assert "then 6 qubits and 7 pairs (the manifest), now 5 qubits and 5 pairs (the read)" in stop["problems"][0]


def test_the_same_layout_listed_another_way_lets_the_job_go(tmp_path):
    seen = []
    path = manifest(tmp_path / "m", QASM, layout=Layout.of(5, NEW).fields)
    flipped = [(b, a) for a, b in reversed(NEW)]
    code, _lines = send(path, Portal(5, flipped, seen), places_in(tmp_path), FakeClock(), max_order=1)
    assert code == 0 and len(posts(seen)) == 1


def test_without_a_pin_there_is_no_check_and_the_read_line_holds_the_layout(tmp_path):
    code, lines = send(manifest(tmp_path / "m", QASM), Portal(5, NEW, []), places_in(tmp_path), FakeClock(),
                       max_order=1)
    read = next(e for e in lines if e["event"] == "read")["read"]
    assert code == 0 and {key: read[key] for key in layout.KEYS} == Layout.of(5, NEW).fields


def test_the_dry_run_compares_the_pin_with_the_saved_read(tmp_path):
    places, out = places_in(tmp_path), []
    path = manifest(tmp_path / "m", QASM, layout=Layout.of(6, OLD).fields)
    assert dryrun.dry_run(path, cfg=cfg(), places=places, clock=FakeClock(), say=out.append) == 0
    assert any("the layout pin of the manifest is compared with a read only" in line for line in out)
    (places.reads / "euroqexa").mkdir(parents=True)
    saved = {"read_at": "2026-01-05T11:00:00+00:00", "machine": "M1", **Layout.of(5, NEW).fields}
    (places.reads / "euroqexa" / "read_20260105T110000Z.json").write_text(json.dumps(saved))
    out.clear()
    assert dryrun.dry_run(path, cfg=cfg(), places=places, clock=FakeClock(), say=out.append) == 1
    assert any(line.startswith("  FAILED: the layout of the machine is not the one the manifest pins: then 6 qubits "
                               "and 7 pairs (the manifest), now 5 qubits and 5 pairs") for line in out)
    path = manifest(tmp_path / "m", QASM, layout=Layout.of(5, NEW).fields)
    assert dryrun.dry_run(path, cfg=cfg(), places=places, clock=FakeClock(), say=out.append) == 0


def test_with_no_saved_read_the_dry_run_still_checks_the_form_of_the_pin(tmp_path):
    out, upper = [], {**Layout.of(5, NEW).fields, "layout_sha256": Layout.of(5, NEW).fields["layout_sha256"].upper()}
    for pin in ("abc", upper):
        path = manifest(tmp_path / "m", QASM, layout=pin)
        assert dryrun.dry_run(path, cfg=cfg(), places=places_in(tmp_path), clock=FakeClock(), say=out.append) == 1
        assert any(line.startswith('  FAILED: "layout" must be {"layout_sha256": 64 hex digits') for line in out)
        out.clear()


def test_a_pin_in_another_form_or_a_read_with_no_layout_is_a_problem():
    assert Pin(None).problems({}) == [] and Pin(None).form_problems == []
    assert Pin(Layout.of(5, NEW).fields).form_problems == []
    assert Pin({**Layout.of(5, NEW).fields, "layout_sha256": "ab" * 31}).form_problems     # only the digest is wrong
    assert '"layout" must be' in Pin({"layout_sha256": "abc", "qubits": 5, "pairs": 5}).problems({})[0]
    assert "cannot be checked" in Pin(Layout.of(5, NEW).fields).problems({"machine": "M1", "qubits": 5})[0]


def test_at_a_site_whose_read_gives_no_layout_the_key_is_a_fact_that_the_dry_run_and_a_send_pass(tmp_path):
    places, clock, out, broker = places_in(tmp_path), FakeClock(), [], Broker()
    path = write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 10),), text=PAYLOAD, layout="x")
    assert dryrun.dry_run(path, cfg=cfg(), places=places, clock=clock, say=out.append) == 0
    assert not any("layout pin" in line or '"layout" must be' in line for line in out)
    assert send_to(path, broker.site(), places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    assert broker.count("POST", "/tasks") == 1 and events(rec, "start")[0]["extra"] == {"layout": "x"}
    assert [e["order"] for e in events(rec, "result")] == [1]
