"""The full text of every refusal of a live call (runner.send), from its arguments to its record."""

import shutil
from functools import partial
from pathlib import Path

import pytest
from fakes import FakeClock, FakeSite, cfg, places_in, records_of, send, write_manifest
from fakes.older import write
from runner_calls import RULES_A, RULES_B

from qdevices import runner


def files_below(root: Path) -> dict:
    """The bytes of every file below `root`, but those of the lock folders."""
    return {p: p.read_bytes() for p in sorted(root.rglob("*"))
            if p.is_file() and "state" not in p.relative_to(root).parts}


def refusals(root: Path, clock):
    """A live call that must be refused: its text, checked to change no file and to ask the site nothing."""
    def refused(places, manifest, site=None, conf=None, **kw) -> str:
        site = FakeSite() if site is None else site
        before = files_below(root)
        with pytest.raises(runner.Refused) as caught:
            send(manifest, site, places, clock, conf, **kw)
        assert files_below(root) == before and site.calls == []
        return str(caught.value)
    return refused


def table(rows) -> str:
    return "".join(f"{case}:\n  {text}\n" for case, text in rows)


def with_older(folder: Path) -> dict:
    """The config of the tests, with this folder of older records for Euro-Q-Exa."""
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], "older_records": [str(folder)]}
    return conf


def test_refusals_of_the_stage_the_manifest_and_the_config(tmp_path, places, clock, golden):
    refused = refusals(tmp_path, clock)
    m = write_manifest(tmp_path / "m")
    no_budget, zone = cfg(), cfg()
    no_budget["vlq"] = {**no_budget["vlq"], "budget_seconds": None}
    zone["piastq"] = {**zone["piastq"], "window": ["Mon 09:00-12:00"], "window_zone": "Nowhere/Never"}
    vlq = write_manifest(tmp_path / "v", site="vlq", project="OTHER", lexis_project="SOMEONE-ELSE")
    rows = [("no --max-order and no --resume", refused(places, m)),
            ("--new-run with --resume", refused(places, m, resume=tmp_path / "absent.jsonl", new_run=True)),
            ("--new-rules with no --resume", refused(places, m, max_order=1, new_rules=True)),
            ("a manifest that fails",
             refused(places, write_manifest(tmp_path / "old", format="qdevices/0"), max_order=1)),
            ("a site object of another site", refused(places, m, FakeSite("vlq"), max_order=1)),
            ("--max-order past the last order", refused(places, m, max_order=4)),
            ("a project not listed", refused(places, write_manifest(tmp_path / "p", project="OTHER"), max_order=1)),
            ("a VLQ project and LEXIS project not listed, and no budget_seconds",
             refused(places, vlq, FakeSite("vlq", seconds_left=3600), no_budget, max_order=1)),
            ("a window zone that is not known",
             refused(places, write_manifest(tmp_path / "w", site="piastq"), FakeSite("piastq"), zone, max_order=1))]
    golden("send_refused_arguments", table(rows))


def test_refusals_of_a_resume(tmp_path, clock, golden):
    refused = refusals(tmp_path, clock)
    a = places_in(tmp_path / "a")
    m = write_manifest(tmp_path / "a" / "m")
    assert send(m, FakeSite(), a, clock, max_order=1, rules_file=RULES_A) == 0            # held to rules_a.py
    rec = records_of(a)[0]
    copy = tmp_path / "elsewhere" / rec.name
    copy.parent.mkdir()
    shutil.copy(rec, copy)
    no_start = write(tmp_path / "x" / "no_start.jsonl", [{"event": "submitting", "order": 1, "name": "J1"}])
    at = partial(refused, a, m, resume=rec, max_order=2)
    rows = [("a record that does not exist", refused(a, m, resume=tmp_path / "absent.jsonl", max_order=2)),
            ("a record with no start line", refused(a, m, resume=no_start)),
            ("a record made with another manifest",
             refused(a, write_manifest(tmp_path / "c" / "m", note="changed"), resume=rec, max_order=2)),
            ("a copy of the record in another folder", refused(a, m, resume=copy, max_order=2)),
            ("a record started on another host", at(host="login-node")),
            ("another rules file than the one the record is held to", at(rules_file=RULES_B)),
            ("no rules file for a record held to one", at()),
            ("the rules file of the record, changed in place", at(rules_file={**RULES_A, "sha256": "c" * 64}))]
    z = places_in(tmp_path / "z")
    mz = write_manifest(tmp_path / "z" / "m")
    assert send(mz, FakeSite(), z, clock, max_order=1) == 0                                # held to no rules file
    rows.append(("a rules file for a record held to none",
                 refused(z, mz, resume=records_of(z)[0], max_order=2, rules_file=RULES_A)))
    n = places_in(tmp_path / "n")
    mn = write_manifest(tmp_path / "n" / "m")
    assert send(mn, FakeSite(), n, clock, max_order=1) == 0
    old = records_of(n)[0]
    clock.t += 5
    assert send(mn, FakeSite(), n, clock, max_order=1, new_run=True) == 0
    rows.append(("an older record of its run", refused(n, mn, resume=old, max_order=2)))
    i = places_in(tmp_path / "i")
    mi = write_manifest(tmp_path / "i" / "m")
    assert send(mi, FakeSite(), i, clock, max_order=1) == 0
    moved = records_of(i)[0]
    shutil.copy(moved, tmp_path / "i" / "copy.jsonl")
    moved.unlink()
    shutil.move(tmp_path / "i" / "copy.jsonl", moved)                                     # the same path, another inode
    rows.append(("a record with another inode at its path", refused(i, mi, resume=moved, max_order=2)))
    golden("send_refused_resume", table(rows))


def test_refusals_of_a_new_record(tmp_path, clock, golden):
    refused = refusals(tmp_path, clock)
    p = places_in(tmp_path / "p")
    mp = write_manifest(tmp_path / "p" / "m")
    assert send(mp, FakeSite(submits={1: ("noanswer",)}), p, clock, max_order=1) == 2      # order 1 lost
    write(tmp_path / "older" / "run3_20261001T000000Z.jsonl",
          [{"event": "submitted", "order": 4, "uuid": "u-4", "machine": "EQE1"}])         # order 4 open
    rows = [("an order lost in a record of the app, and one open in an older record",
             refused(p, mp, conf=with_older(tmp_path / "older"), max_order=1))]
    q = places_in(tmp_path / "q")
    rows.append(("an older record folder that does not exist",
                 refused(q, write_manifest(tmp_path / "q" / "m"), conf=with_older(tmp_path / "absent"), max_order=1)))
    d = places_in(tmp_path / "d")
    (d.records / "euroqexa" / "older_decisions.jsonl").mkdir(parents=True)
    (tmp_path / "empty").mkdir()
    rows.append(("a decisions path that is a folder",
                 refused(d, write_manifest(tmp_path / "d" / "m"), conf=with_older(tmp_path / "empty"), max_order=1)))
    e = places_in(tmp_path / "e")
    me = write_manifest(tmp_path / "e" / "m")
    assert send(me, FakeSite(), e, clock, max_order=1) == 0
    rows.append(("an earlier record of the run with jobs that were sent", refused(e, me, max_order=1)))
    s = places_in(tmp_path / "s")
    ms = write_manifest(tmp_path / "s" / "m")
    assert send(ms, FakeSite(max_shots=5), s, FakeClock(), max_order=1) == 2                # a rule stopped it: unsent
    rows.append(("a new record in the second of a record of the run",
                 refusals(tmp_path, FakeClock())(s, ms, max_order=1)))
    golden("send_refused_new_record", table(rows))
