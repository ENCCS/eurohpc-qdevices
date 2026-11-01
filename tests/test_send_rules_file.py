"""The rules file in the record: its SHA-256 on the start and resume lines, and --new-rules for a resume."""

import hashlib
import json
import shlex

import pytest
from fakes import CONFIG, TOKEN, FakeClock, FakeSite, cfg, events, lines_of, places_in, records_of, send, write_manifest

from qdevices import cli, runner

A = {"path": "rules_a.py", "sha256": "a" * 64}         # synthetic: the form rulebook.load gives
B = {"path": "rules_b.py", "sha256": "b" * 64}


def started(tmp_path, places, clock, rules_file):
    """A record whose first call sent order 1 with this rules file."""
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1, rules_file=rules_file) == 0
    return m, records_of(places)[0]


def old_record(tmp_path, places, clock, resumed=False):
    """A record as an older version wrote it, with no rules field on any line. Rewritten in place."""
    m, rec = started(tmp_path, places, clock, A)
    if resumed:
        assert send(m, FakeSite(), places, clock, resume=rec, max_order=1, rules_file=A) == 0
    keys = ("rules_file", "new_rules", "rules_note")
    lines = [{k: v for k, v in line.items() if k not in keys} for line in lines_of(rec)]
    rec.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return m, rec


def test_the_start_and_resume_lines_hold_the_rules_file(tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock, A)
    assert events(rec, "start")[0]["rules_file"] == A
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=2, rules_file=dict(A)) == 0
    line = events(rec, "resume")[0]
    assert line["rules_file"] == A and line["new_rules"] is False
    assert "rules_before" not in line and "rules_note" not in line


@pytest.mark.parametrize("first, then, way", [
    (A, B, "Give --rules rules_a.py to send"),
    (None, A, "Leave out --rules to send"),
    (A, None, "Give --rules rules_a.py to send"),
    (A, {**A, "sha256": "c" * 64},                     # the same path, another SHA-256: the file changed in place
     f"rules_a.py has changed since the record was held to it: put back the file with SHA-256 {'a' * 64} to send"),
], ids=["other", "none-then-one", "one-then-none", "changed-in-place"])
def test_a_resume_that_sends_with_other_rules_is_refused_and_sends_nothing(tmp_path, places, clock, first, then, way):
    m, rec = started(tmp_path, places, clock, first)
    before = rec.read_text()
    site = FakeSite()
    with pytest.raises(runner.Refused, match="--new-rules") as refused:
        send(m, site, places, clock, resume=rec, max_order=2, rules_file=then)
    assert way in str(refused.value)                   # first the way on with the rules the record is held to
    assert site.calls == [] and rec.read_text() == before


def test_new_rules_lets_a_resume_send_and_its_line_holds_both(tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock, A)
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, max_order=2, rules_file=B, new_rules=True) == 0
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 2)]
    line = events(rec, "resume")[0]
    assert line["new_rules"] is True and line["rules_file"] == B and line["rules_before"] == A
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=3, rules_file=B) == 0      # held to B now
    with pytest.raises(runner.Refused, match="--new-rules"):
        send(m, FakeSite(), places, clock, resume=rec, max_order=3, rules_file=A)


def test_a_start_with_no_rules_file_holds_the_record_to_none(tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock, None)
    assert events(rec, "start")[0]["rules_file"] is None
    with pytest.raises(runner.Refused, match="held to no rules file"):
        send(m, FakeSite(), places, clock, resume=rec, max_order=2, rules_file=A)
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=2, rules_file=A, new_rules=True) == 0
    line = events(rec, "resume")[0]
    assert line["rules_file"] == A and line["rules_before"] is None


@pytest.mark.parametrize("then", [B, None], ids=["other", "none"])
def test_a_resume_that_collects_only_is_never_refused(tmp_path, places, clock, then):
    m, rec = started(tmp_path, places, clock, A)
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, rules_file=then) == 0
    assert not [c for c in site.calls if c[0] in ("submit", "prepare", "read")]
    line = events(rec, "resume")[0]
    assert line["max_order"] is None and line["rules_file"] == then and "rules_note" in line


def test_new_rules_without_resume_is_refused(tmp_path, places, clock):
    site = FakeSite()
    with pytest.raises(runner.Refused, match="--new-rules goes with --resume"):
        send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, rules_file=A, new_rules=True)
    assert site.calls == [] and not places.records.exists()


def test_an_old_record_with_no_rules_field_is_resumed_with_a_note(tmp_path, places, clock):
    m, rec = old_record(tmp_path, places, clock)
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, max_order=2, rules_file=B) == 0
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 2)]
    line = events(rec, "resume")[0]
    assert line["rules_file"] == B and line["new_rules"] is False and "older version" in line["rules_note"]


def test_the_first_resume_of_an_old_record_holds_it_to_its_rules_file(tmp_path, places, clock):
    m, rec = old_record(tmp_path, places, clock, resumed=True)        # with a resume line of the older version
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=2, rules_file=B) == 0
    assert "older version" in events(rec, "resume")[-1]["rules_note"]
    before = rec.read_text()
    for then in (A, None):
        site = FakeSite()
        with pytest.raises(runner.Refused, match=r"held to rules_b.py .*Give --rules rules_b.py"):
            send(m, site, places, clock, resume=rec, max_order=3, rules_file=then)
        assert site.calls == [] and rec.read_text() == before
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=3, rules_file=B) == 0


def test_a_resume_that_collects_only_does_not_hold_an_old_record_to_its_rules_file(tmp_path, places, clock):
    m, rec = old_record(tmp_path, places, clock)
    said = []
    for then in (None, A):                                     # two calls that collect only, the first with none
        assert runner.send(m, FakeSite(), cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="host-a",
                           say=said.append, resume=rec, rules_file=then) == 0
        assert "the first resume that sends holds" in events(rec, "resume")[-1]["rules_note"]
    assert said[-1].endswith(" --max-order N --rules rules_a.py")         # the rules file of the call
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=2, rules_file=B) == 0     # not refused: sets B
    assert [e["order"] for e in events(rec, "result")] == [1, 2]
    with pytest.raises(runner.Refused, match=r"held to rules_b.py"):
        send(m, FakeSite(), places, clock, resume=rec, max_order=3)


def test_new_rules_holds_an_old_record_to_a_rules_file_from_then_on(tmp_path, places, clock):
    m, rec = old_record(tmp_path, places, clock)
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=2, rules_file=A, new_rules=True) == 0
    assert "rules_before" not in events(rec, "resume")[0]
    with pytest.raises(runner.Refused, match="--new-rules"):
        send(m, FakeSite(), places, clock, resume=rec, max_order=3, rules_file=B)


@pytest.mark.parametrize("first, then, new_rules, given", [
    (A, B, False, " --rules rules_a.py"),           # this call has another file: the record stays held to A
    (A, B, True, " --rules rules_b.py"),            # --new-rules: held to B from this call on
    (None, A, False, ""),                           # held to no rules file: no --rules
], ids=["held", "new-rules", "none"])
def test_the_next_command_gives_the_rules_file_the_record_is_held_to(tmp_path, places, clock, first, then, new_rules,
                                                                     given):
    m, rec = started(tmp_path, places, clock, first)
    said = []
    assert runner.send(m, FakeSite(), cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="host-a",
                       say=said.append, resume=rec, rules_file=then, new_rules=new_rules) == 0     # collect only
    assert said[-1] == (f"Go on with: qdevices send {shlex.quote(str(m))} --live --resume {shlex.quote(str(rec))} "
                        f"--max-order N{given}")


def test_the_command_line_writes_the_sha256_of_the_rules_file_and_takes_new_rules(tmp_path, capsys):
    places = places_in(tmp_path)
    places.config.write_text(CONFIG)
    m = write_manifest(tmp_path / "m")
    first, second = tmp_path / "first.py", tmp_path / "second.py"
    first.write_text("# the rules of an experiment\n")
    second.write_text("# the rules of an experiment, changed\n")

    def main(*args):
        clock = FakeClock()
        return cli.main(["send", str(m), "--live", *args], places=places, environ={"MQSS_TOKEN": TOKEN},
                        make_site=lambda man, name, token, **kw: FakeSite(name), clock=clock, sleep=clock.sleep,
                        host="host-a")

    assert main("--max-order", "1", "--rules", str(first)) == 0
    rec = records_of(places)[0]
    assert events(rec, "start")[0]["rules_file"] == {"path": str(first.resolve()),
                                                     "sha256": hashlib.sha256(first.read_bytes()).hexdigest()}
    again = ("--resume", str(rec), "--max-order", "2", "--rules", str(second))
    assert main(*again) == 1                                   # refused: another rules file
    assert main(*again, "--new-rules") == 0
    line = events(rec, "resume")[-1]
    assert line["rules_before"]["path"] == str(first.resolve())
    assert line["rules_file"]["sha256"] == hashlib.sha256(second.read_bytes()).hexdigest()
    capsys.readouterr()
    assert main("--max-order", "1", "--new-rules") == 1        # --new-rules goes with --resume
    assert "--new-rules goes with --resume" in capsys.readouterr().out


def test_a_rules_file_that_exits_at_its_import_is_refused_by_the_command_line_and_sends_nothing(tmp_path, capsys):
    places = places_in(tmp_path)
    places.config.write_text(CONFIG)
    rules = tmp_path / "rules.py"
    rules.write_text("import sys\nsys.exit(7)\n")
    clock, site = FakeClock(), FakeSite()
    code = cli.main(["send", str(write_manifest(tmp_path / "m")), "--live", "--max-order", "1", "--rules", str(rules)],
                    places=places, environ={"MQSS_TOKEN": TOKEN}, make_site=lambda man, name, token, **kw: site,
                    clock=clock, sleep=clock.sleep, host="host-a")
    assert code == 1
    assert f"REFUSED: the rules file {rules} cannot be loaded: SystemExit: 7" in capsys.readouterr().out
    assert site.calls == [] and records_of(places) == []
