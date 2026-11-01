"""The opening of a record, the rules file it is held to, the stage, the lock and the signals, faults included."""

import shutil
import signal
from pathlib import Path

import pytest
from fakes import STATE, FakeSite, cfg, events, lines_of, records_of, send, write_manifest
from fakes.older import write
from runner_calls import ctrl_c
from test_call_paths import collect_with, handlers, live, mine, noting, on_disk_at, own_handlers, records_made

from qdevices import manifest, record, rulebook, runner
from qdevices.lock import LockRefused
from qdevices.runner import preflight, resume, rulesfile, signals
from qdevices.screen import quoted
from qdevices.sites import SITES

A = {"path": "rules_a.py", "sha256": "a" * 64}         # synthetic: the form of a rules file in a record
B = {"path": "rules_b.py", "sha256": "b" * 64}
C = {"path": "rules_c.py", "sha256": "c" * 64}
NO_SHA = {"path": "rules_a.py"}
TEXT = "rules_a.py"
LISTED = ["rules_a.py"]
NAMED_A = f"rules_a.py (SHA-256 {'a' * 64})"
NAMED_B = f"rules_b.py (SHA-256 {'b' * 64})"
NAMED_C = f"rules_c.py (SHA-256 {'c' * 64})"
OLDER = "the start line of the record has no rules field (an older version of the app made it)"
GIVE_A = "Give --rules rules_a.py to send with the rules the record is held to"
LEAVE_OUT = "Leave out --rules to send with the rules the record is held to"
COPY = ("It may be a copy, and a copy and its record would each send the same orders. Give --resume without "
        "--max-order to collect only")
CUT = '{"event": "step", "order": 1, "job": 47'        # a line cut inside a job id that is a number
APP_NAME = "run_20260101T000000Z.jsonl"                # the form of the name of a record of the app
BAD_ZONE = {"window": ["Mon 00:00-24:00"], "window_zone": "Not/AZone"}
NO_BUDGET = {"budget_seconds": None}
NAMES = [(signal.SIGTERM, "SIGTERM"), (signal.SIGHUP, "SIGHUP")]


def cut_entry(number, text):
    """The entry of a cut line in a resume line."""
    return resume.cut_entry(number, text)


def held_to(start, prior):
    """Whether a line of a record sets the rules file it is held to, and that file."""
    known, held = rulesfile.RulesFile.held_by(start, prior)
    return known, held.value


def resume_fields(path, start, prior, rules_file, *, new_rules, sending):
    """The rules fields of a resume line and its note; Refused for a resume that may not send."""
    return rulesfile.RulesFile(rules_file).resume_fields(path, start, prior, new_rules=new_rules, sending=sending)


def path_of(rules_file):
    """The path to give with --rules for a rules file."""
    return rulesfile.RulesFile(rules_file).path


def named(rules_file):
    """A rules file as the texts name it."""
    return str(rulesfile.RulesFile(rules_file))


def check_stage(**stage):
    """Refused for a call that names no stage, or two that do not go together."""
    preflight.check_stage(**stage)


def check_arguments(man, site, conf, *, max_order):
    """The config of the site, or Refused for a call that must not start."""
    return preflight.check_arguments(man, site, conf, max_order=max_order)


def catch_kills():
    """Both signals as an interrupt; what they were set to."""
    return signals.KillsAsInterrupt().__enter__()


def restore(earlier):
    """Both signals as they were set."""
    return earlier.__exit__(None, None, None)


def load_rules(path):
    """The hooks of a rules file, with its path and SHA-256."""
    return rulebook.load(path)


def resumed(rules_file, *, max_order=None, new_rules=False) -> dict:
    """A resume line with its rules fields, as a record holds it."""
    return {"event": "resume", "max_order": max_order, "rules_file": rules_file, "new_rules": new_rules}


def started(tmp_path, places, clock, rules_file=None) -> tuple:
    """A record whose first call sent order 1, with a line cut at its end: the manifest and the record."""
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1, rules_file=rules_file) == 0
    rec = records_of(places)[0]
    with open(rec, "a", encoding="utf-8") as fh:
        fh.write(CUT)
    return m, rec


def copied(rec, tmp_path) -> Path:
    """A copy of a record in another folder, with the name of the record."""
    copy = tmp_path / "elsewhere" / rec.name
    copy.parent.mkdir()
    shutil.copy(rec, copy)
    return copy


def another_record(places, seconds) -> Path:
    """A record of the app in another run folder of the site, whose one order ended with a result of these seconds."""
    where = {"order": 1, "name": "J1"}
    return write(places.records / "euroqexa" / "other" / APP_NAME, [
        {"event": "start", "project": "TEST-PROJECT"}, {"event": "submitting", **where},
        {"event": "submitted", **where, "id": "J-1"},
        {"event": "result", **where, "id": "J-1", "shots": 10, "seconds": seconds}])


def refused_text(m, places, clock, target, **kw) -> str:
    """The text of a resume of `target` that is refused; it writes no byte, asks nothing and releases the lock."""
    before, site = target.read_bytes(), FakeSite()
    with pytest.raises(runner.Refused) as refused:
        send(m, site, places, clock, resume=target, **kw)
    assert target.read_bytes() == before and site.calls == []
    assert not (places.state / "euroqexa.holder").exists()
    return str(refused.value)


def loaded(tmp_path, **head) -> dict:
    """The manifest of three jobs as a call reads it, with these keys in its head."""
    return manifest.load(write_manifest(tmp_path / "m", **head), SITES)


def conf_with(**keys) -> dict:
    """The config of the tests with these keys for Euro-Q-Exa."""
    conf = cfg()
    conf["euroqexa"] = {**conf["euroqexa"], **keys}
    return conf


def on_mine() -> bool:
    """True when both signals have the handler of the test."""
    return handlers() == [mine, mine]


def lock_of_test(phases: list):
    """A take_lock that notes, at its take and at its release, if both signals have the handler of the test."""
    def take(site: str):
        phases.append((f"taken {site}", on_mine()))
        return lambda: phases.append((f"released {site}", on_mine()))

    return take


@pytest.mark.parametrize("text, found", [
    ('{"event": "submitted", "id": "J-4711", "submitted_utc": "', {"job_id": "J-4711", "job_id_may_be_cut": False}),
    ('{"event": "submitted", "id": "J-47', {"job_id": "J-47", "job_id_may_be_cut": True}),
    ('{"event": "step", "job": 4711, "step": "crea', {"job_id": "4711", "job_id_may_be_cut": False}),
    ('{"event": "step", "job": 47', {"job_id": "47", "job_id_may_be_cut": True}),
    ('{"event": "submitted", "id": "", "submitted_utc": "', {}),
    ('{"event": "submitted", "id": "', {}),
    ('{"event": "rule", "id": null, "rule": "sho', {}),
    ('{"event": "rule", "rule": "sho', {}),
    ('{"job": 7, "id": "J-1", "z', {"job_id": "7", "job_id_may_be_cut": False}),
    ('{"id": "a\\"', {"job_id": 'a\\"', "job_id_may_be_cut": True}),       # fault 16, fixed: this id is cut
], ids=["text closed", "text cut", "number in the middle", "number at the end", "empty", "only its first quote",
        "null", "no id", "the first of two", "cut after an escaped quote"])
def test_a_cut_line_gives_its_number_its_text_and_any_job_id_it_holds(text, found):
    assert list(cut_entry(7, text).items()) == [("line", 7), ("text", text), *found.items()]


def test_the_text_of_a_cut_line_is_cut_to_120_characters_and_its_id_is_read_from_the_whole_line():
    text = '{"note": "' + "x" * 200 + '", "id": "J-1", "z'
    entry = cut_entry(3, text)
    assert entry == {"line": 3, "text": text[:120], "job_id": "J-1", "job_id_may_be_cut": False}
    assert len(entry["text"]) == 120


HELD = [
    ("an older start", {}, [], False, None),
    ("no rules file", {"rules_file": None}, [], True, None),
    ("a file", {"rules_file": A}, [], True, A),
    ("no sha256", {"rules_file": NO_SHA}, [], True, NO_SHA),
    ("a text", {"rules_file": TEXT}, [], True, TEXT),
    ("a list", {"rules_file": LISTED}, [], True, LISTED),
    ("an older start, a resume that collected", {}, [resumed(B)], False, None),
    ("an older start, a resume that sent", {}, [resumed(B, max_order=2)], True, B),
    ("an older start, a resume with max_order 0", {}, [resumed(B, max_order=0)], True, B),
    ("an older start, the first that sent", {}, [resumed(A), resumed(B, max_order=2), resumed(C, max_order=3)], True,
     B),
    ("an older start, a resume with no rules field", {}, [{"event": "resume", "max_order": 2}], False, None),
    ("an older start, new rules that collected", {}, [resumed(B, new_rules=True)], True, B),
    ("a start, a resume that sent with another", {"rules_file": A}, [resumed(B, max_order=2)], True, A),
    ("a start, new rules", {"rules_file": A}, [resumed(B, new_rules=True)], True, B),
    ("a start, the last new rules", {"rules_file": A},
     [resumed(B, new_rules=True, max_order=2), resumed(C, new_rules=True)], True, C),
    ("a start, new rules, then a resume that sent", {"rules_file": A},
     [resumed(B, new_rules=True), resumed(C, max_order=3)], True, B),
    ("a start, new_rules that is not True", {"rules_file": A}, [{**resumed(B), "new_rules": 1}], True, A),
    ("a start, another event", {"rules_file": A}, [{"event": "read", "rules_file": B, "new_rules": True}], True, A),
]


@pytest.mark.parametrize("start, prior, known, held", [row[1:] for row in HELD], ids=[row[0] for row in HELD])
def test_what_is_known_of_the_rules_file_of_a_record_and_what_it_is_held_to(start, prior, known, held):
    assert held_to(start, prior) == (known, held)


@pytest.mark.parametrize("value, path, name", [
    (None, None, "no rules file"),
    (A, "rules_a.py", NAMED_A),
    (NO_SHA, None, "no rules file"),
    (TEXT, None, "no rules file"),
    (LISTED, None, "no rules file"),
    ({"sha256": "a" * 64}, None, f"None (SHA-256 {'a' * 64})"),
    ({"path": "x.py", "sha256": ""}, "x.py", "x.py (SHA-256 )"),
    ({"path": "x.py", "sha256": None}, None, "no rules file"),
], ids=["None", "a file", "no sha256", "a text", "a list", "no path", "an empty sha256", "a sha256 of None"])
def test_the_path_and_the_name_of_each_form_of_a_rules_file(value, path, name):
    assert path_of(value) == path
    assert named(value) == name


FROM_B = f"{OLDER}: from this call on the record is held to {NAMED_B}"
FIELDS = [
    ("an older start, sends", {}, [], B, False, True, [], FROM_B),
    ("an older start, new rules, collects", {}, [], B, True, False, [], FROM_B),
    ("an older start, collects", {}, [], B, False, False, [],
     f"{OLDER}: this call collects only, with {NAMED_B}; the first resume that sends holds the record to its "
     "rules file"),
    ("an older start, collects with no file", {}, [], None, False, False, [],
     f"{OLDER}: this call collects only, with no rules file; the first resume that sends holds the record to its "
     "rules file"),
    ("an older start, a resume that collected, sends", {}, [resumed(A)], B, False, True, [], FROM_B),
    ("an older start, held by a resume that sent", {}, [resumed(B, max_order=2)], B, False, True, [], None),
    ("the same file", {"rules_file": A}, [], dict(A), False, True, [], None),
    ("the same SHA-256 at another path", {"rules_file": A}, [], {**A, "path": "moved.py"}, False, True, [], None),
    ("the same file, new rules", {"rules_file": A}, [], A, True, True, [("rules_before", A)], None),
    ("another file, new rules", {"rules_file": A}, [], B, True, True, [("rules_before", A)],
     f"--new-rules: from this call on the record is held to {NAMED_B}, not {NAMED_A}"),
    ("another file, collects", {"rules_file": A}, [], B, False, False, [],
     f"the record is held to {NAMED_A}; this call collects only, with {NAMED_B}"),
    ("no rules file, none given", {"rules_file": None}, [], None, False, True, [], None),
    ("no rules file, new rules", {"rules_file": None}, [], A, True, True, [("rules_before", None)],
     f"--new-rules: from this call on the record is held to {NAMED_A}, not no rules file"),
    ("no sha256, none given", {"rules_file": NO_SHA}, [], None, False, True, [], None),
    ("a text, none given", {"rules_file": TEXT}, [], None, False, True, [], None),
    ("a list, none given", {"rules_file": LISTED}, [], None, False, True, [], None),
    ("a text, new rules", {"rules_file": TEXT}, [], A, True, True, [("rules_before", TEXT)],
     f"--new-rules: from this call on the record is held to {NAMED_A}, not no rules file"),
    ("no sha256, collects with a file", {"rules_file": NO_SHA}, [], A, False, False, [],
     f"the record is held to no rules file; this call collects only, with {NAMED_A}"),
    ("new rules before, that file", {"rules_file": A}, [resumed(B, new_rules=True)], B, False, True, [], None),
    ("new rules before, new rules again", {"rules_file": A}, [resumed(B, new_rules=True)], C, True, True,
     [("rules_before", B)], f"--new-rules: from this call on the record is held to {NAMED_C}, not {NAMED_B}"),
]


@pytest.mark.parametrize("start, prior, rules_file, new_rules, sending, before, note", [row[1:] for row in FIELDS],
                         ids=[row[0] for row in FIELDS])
def test_the_rules_fields_of_a_resume_line_in_their_order_and_its_note(
        start, prior, rules_file, new_rules, sending, before, note):
    fields, said = resume_fields("run.jsonl", start, prior, rules_file, new_rules=new_rules, sending=sending)
    assert list(fields.items()) == [("rules_file", rules_file), ("new_rules", new_rules), *before,
                                    *([("rules_note", note)] if note else [])]
    assert said == note


@pytest.mark.parametrize("held, given, way", [
    (None, A, LEAVE_OUT),
    (NO_SHA, A, LEAVE_OUT),
    (TEXT, A, LEAVE_OUT),
    (LISTED, A, LEAVE_OUT),
    (A, {**A, "sha256": "c" * 64},
     f"rules_a.py has changed since the record was held to it: put back the file with SHA-256 {'a' * 64} to send with "
     "those rules"),
    (A, B, GIVE_A),
    (A, None, GIVE_A),
    (A, NO_SHA, GIVE_A),
    ({"path": "my rules.py", "sha256": "a" * 64}, B,
     "Give --rules 'my rules.py' to send with the rules the record is held to"),
], ids=["no rules file", "no sha256", "a text", "a list", "changed in place", "another file", "none given",
        "none with a path given", "a path with a space"])
def test_the_text_of_a_refused_resume_with_each_of_its_ways_on(held, given, way):
    with pytest.raises(runner.Refused) as refused:
        resume_fields("run.jsonl", {"rules_file": held}, [], given, new_rules=False, sending=True)
    assert str(refused.value) == (
        f"run.jsonl sends nothing with this rules file: the record is held to {named(held)}, and this call gives "
        f"{named(given)}. {way}; give --new-rules to change the rules from here on (the resume line then holds both), "
        "or --resume without --max-order to collect only")


def test_the_keys_of_a_resume_line_with_new_rules_in_their_order(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1, rules_file=A) == 0
    rec = records_of(places)[0]
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=2, rules_file=B, new_rules=True) == 0
    assert list(events(rec, "resume")[0]) == ["event", "utc", "app", "site", "machine", "project", "max_order", "host",
                                              "version", "cut_lines", "rules_file", "new_rules", "rules_before",
                                              "rules_note"]


@pytest.mark.parametrize("form", [NO_SHA, TEXT, LISTED], ids=["no sha256", "a text", "a list"])
def test_a_start_line_with_no_sha256_in_its_rules_file_holds_a_resume_to_no_rules_file(tmp_path, places, clock, form):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1, rules_file=form) == 0
    rec = records_of(places)[0]
    assert events(rec, "start")[0]["rules_file"] == form
    site, said = FakeSite(), []
    assert live(m, site, places, clock, said.append, resume=rec, max_order=2) == 0
    assert ("submit", 2) in site.calls
    assert said[-1].endswith(" --max-order N")


@pytest.mark.parametrize("first, then, new_rules, given", [
    (A, B, False, " --rules rules_a.py"),
    (A, B, True, " --rules rules_b.py"),
    (None, None, False, ""),
], ids=["held", "new rules", "none"])
def test_the_collect_command_of_a_resume_gives_the_rules_file_the_record_is_held_to(
        tmp_path, places, clock, first, then, new_rules, given):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(states={"J-1": [STATE()]}), places, clock, max_order=1, rules_file=first) == 2
    rec = records_of(places)[0]
    site, said = FakeSite(states={"J-1": [ctrl_c]}), []
    assert live(m, site, places, clock, said.append, resume=rec, rules_file=then, new_rules=new_rules) == 130
    assert said[-2] == collect_with(m, rec) + given


def test_the_notes_of_a_resume_come_in_their_order_before_the_first_order(tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock, A)
    copy = copied(rec, tmp_path)
    number, said = copy.read_bytes().count(b"\n") + 1, []
    assert live(m, FakeSite(), places, clock, said.append, resume=copy, rules_file=B) == 0
    assert said[:5] == [f"NOTE: {copy} is not in the records folder; it is collected only",
                        f"NOTE: line {number} of the record is cut and is not read: {CUT}",
                        f"NOTE: line {number} holds the job id 47; the id may be cut, as the line ends in it",
                        f"NOTE: the record is held to {NAMED_A}; this call collects only, with {NAMED_B}",
                        "[1/3] J1: result in the record, not sent again"]
    resume = next(e for e in record.RecordLines.read(copy).events if e["event"] == "resume")
    assert resume["cut_lines"] == [{"line": number, "text": CUT, "job_id": "47", "job_id_may_be_cut": True}]


def test_the_notes_of_the_cut_line_and_of_the_rules_file_come_after_the_resume_line(tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock, A)
    seen = []
    assert live(m, FakeSite(), places, clock, noting(places, seen), resume=rec, rules_file=B) == 0
    assert on_disk_at(seen, "NOTE:") == ["resume"] * 3


def test_a_call_that_only_collects_reads_no_other_record_and_a_call_that_sends_counts_its_seconds(
        tmp_path, places, clock, monkeypatch):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1) == 0
    rec, other = records_of(places)[0], another_record(places, 5.0)
    read_bytes = Path.read_bytes

    def denied(path):
        if path == other:
            raise PermissionError(13, "Permission denied")
        return read_bytes(path)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "read_bytes", denied)
        assert send(m, FakeSite(), places, clock, resume=rec) == 0
        with pytest.raises(runner.Refused, match="cannot be read: PermissionError"):
            send(m, FakeSite(), places, clock, resume=rec, max_order=2)
    assert events(rec, "end")[-1]["used_seconds"] == 1.5
    assert send(m, FakeSite(), places, clock, resume=rec, max_order=2) == 0
    assert events(rec, "end")[-1]["used_seconds"] == 8.0        # 5.0 elsewhere, then 1.5 for each order of this record


def test_a_resume_refused_for_its_rules_file_writes_nothing(tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock, A)
    text = refused_text(m, places, clock, rec, max_order=2, rules_file=B)
    assert text.startswith(f"{rec} sends nothing with this rules file: the record is held to {NAMED_A}, ")


@pytest.mark.parametrize("stage", [{"max_order": 2}, {}], ids=["sends", "collects"])
def test_a_resume_refused_for_another_manifest_writes_nothing(tmp_path, places, clock, stage):
    _, rec = started(tmp_path, places, clock)
    other = write_manifest(tmp_path / "other", experiment="another")
    assert refused_text(other, places, clock, rec, **stage) == (
        f"{rec} was made with another manifest or other files; it cannot be continued")


def test_a_resume_refused_as_a_copy_joins_its_problems_in_their_order_and_writes_nothing(tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock)
    copy, before = copied(rec, tmp_path), rec.read_bytes()
    folder = (places.records / "euroqexa" / "m").resolve()
    assert refused_text(m, places, clock, copy, max_order=2, host="host-b") == (
        f"{copy} sends nothing: it is not a record of the run folder {folder}; its path, device or inode is not the "
        f"one of its start line; it was started on the host 'host-a', this is 'host-b'. {COPY}")
    assert rec.read_bytes() == before


def test_a_resume_of_a_record_that_is_not_the_newest_joins_that_and_the_host(tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock)
    clock.t += 5
    assert send(m, FakeSite(), places, clock, max_order=1, new_run=True) == 0
    folder = (places.records / "euroqexa" / "m").resolve()
    assert refused_text(m, places, clock, rec, max_order=2, host="host-b") == (
        f"{rec} sends nothing: it is not the newest record of {folder}; it was started on the host 'host-a', this is "
        f"'host-b'. {COPY}")


def test_a_resume_with_several_faults_is_refused_for_the_manifest_then_the_copy_then_the_rules_file(
        tmp_path, places, clock):
    m, rec = started(tmp_path, places, clock, A)
    copy = copied(rec, tmp_path)
    other = write_manifest(tmp_path / "other", experiment="another")
    assert refused_text(other, places, clock, copy, max_order=2, rules_file=B).endswith(
        "was made with another manifest or other files; it cannot be continued")
    assert refused_text(m, places, clock, copy, max_order=2, rules_file=B).startswith(
        f"{copy} sends nothing: it is not a record of the run folder ")


NEEDS = "a live call needs --max-order N or --resume FILE; nothing is sent"
NEW_RUN = "--new-run starts a new record; it does not go with --resume"
NEW_RULES = "--new-rules goes with --resume: a new record is held to the rules file of its own call"


@pytest.mark.parametrize("stage, text", [
    ({"max_order": None, "resume": None, "new_run": False}, NEEDS),
    ({"max_order": None, "resume": None, "new_run": True, "new_rules": True}, NEEDS),
    ({"max_order": 1, "resume": "r", "new_run": True}, NEW_RUN),
    ({"max_order": None, "resume": "r", "new_run": True, "new_rules": True}, NEW_RUN),
    ({"max_order": 1, "resume": None, "new_run": False, "new_rules": True}, NEW_RULES),
    ({"max_order": 1, "resume": None, "new_run": True, "new_rules": True}, NEW_RULES),
], ids=["no stage", "no stage first", "new run with resume", "new run first", "new rules with no resume",
        "new rules with new run"])
def test_each_refusal_of_the_stage_and_the_first_of_two(stage, text):
    with pytest.raises(runner.Refused) as refused:
        check_stage(**stage)
    assert str(refused.value) == text


@pytest.mark.parametrize("stage", [
    {"max_order": 1, "resume": None, "new_run": False},
    {"max_order": 1, "resume": None, "new_run": True},
    {"max_order": None, "resume": "r", "new_run": False},
    {"max_order": None, "resume": "r", "new_run": False, "new_rules": True},
    {"max_order": 0, "resume": None, "new_run": False},
], ids=["max order", "new run", "resume", "new rules", "max order 0"])
def test_a_stage_that_goes_together_passes(stage):
    assert check_stage(**stage) is None


PROJECT = "the project 'OTHER' is not listed for euroqexa in qdevices.toml"
BUDGET = "no budget_seconds for euroqexa in qdevices.toml: the budget rule needs it"
ZONE = "the window zone 'Not/AZone' is not known"


@pytest.mark.parametrize("site, project, keys, max_order, text", [
    ("vlq", "OTHER", {**NO_BUDGET, **BAD_ZONE}, 9, "the manifest is for euroqexa, the site object is vlq"),
    ("euroqexa", "OTHER", {**NO_BUDGET, **BAD_ZONE}, 9, "--max-order 9: the manifest has the orders 1 to 3"),
    ("euroqexa", "OTHER", {**NO_BUDGET, **BAD_ZONE}, 0, "--max-order 0: the manifest has the orders 1 to 3"),
    ("euroqexa", "OTHER", {**NO_BUDGET, **BAD_ZONE}, 1, f"{PROJECT}; {BUDGET}"),
    ("euroqexa", "OTHER", BAD_ZONE, 1, PROJECT),
    ("euroqexa", "TEST-PROJECT", {**NO_BUDGET, **BAD_ZONE}, 1, BUDGET),
    ("euroqexa", "TEST-PROJECT", BAD_ZONE, 1, ZONE),
    ("euroqexa", "OTHER", {**NO_BUDGET, **BAD_ZONE}, None, ZONE),
    ("euroqexa", "TEST-PROJECT", {"window": ["Mon 00:00-24:00"], "window_zone": "../x"}, None,
     "the window zone '../x' is not known"),
], ids=["the site", "max order above", "max order 0", "project and budget joined", "project", "budget", "zone",
        "no max order: only the zone", "a zone that is no key"])
def test_check_arguments_refuses_for_the_first_fault_in_its_order(tmp_path, site, project, keys, max_order, text):
    with pytest.raises(runner.Refused) as refused:
        check_arguments(loaded(tmp_path, project=project), FakeSite(site), conf_with(**keys), max_order=max_order)
    assert str(refused.value) == text


@pytest.mark.parametrize("project, keys, max_order", [
    ("TEST-PROJECT", {}, 1),
    ("TEST-PROJECT", {}, 3),
    ("TEST-PROJECT", {"budget_seconds": 0}, 1),
    ("OTHER", NO_BUDGET, None),
    ("TEST-PROJECT", {"window_zone": "Not/AZone"}, 1),
    ("TEST-PROJECT", {"window": ["Mon 00:00-24:00"], "window_zone": "UTC"}, 1),
], ids=["max order 1", "the last order", "a budget of 0", "no max order", "a zone with no window", "a known zone"])
def test_check_arguments_gives_the_config_of_the_site(tmp_path, project, keys, max_order):
    conf = conf_with(**keys)
    man = loaded(tmp_path, project=project)
    assert check_arguments(man, FakeSite(), conf, max_order=max_order) == conf["euroqexa"]


@pytest.mark.parametrize("stage", [{}, {"max_order": 9}, {"max_order": 1, "new_rules": True}],
                         ids=["no stage", "an order above the manifest", "new rules with no resume"])
def test_the_stage_and_the_arguments_are_checked_before_the_lock_is_asked_for(tmp_path, places, clock, stage):
    def never(site):
        raise AssertionError("the lock was asked for")

    with pytest.raises(runner.Refused):
        send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, take_lock=never, **stage)
    assert not places.state.exists()


@pytest.mark.parametrize("answers, code", [
    ({}, 0), ({"max_shots": 5}, 2), ({"submits": {1: ("crash",)}}, 3), ({"submits": {1: ("interrupt",)}}, 130),
], ids=["an end", "a stop", "an error of the program", "an interrupt"])
def test_the_lock_sees_the_earlier_handlers_and_the_open_record_those_of_the_app(
        tmp_path, places, clock, answers, code):
    own_handlers()
    phases = []

    def say(text):
        phases.append(("say", on_mine()))

    m = write_manifest(tmp_path / "m")
    assert live(m, FakeSite(**answers), places, clock, say, max_order=1, take_lock=lock_of_test(phases)) == code
    assert phases[0] == ("taken euroqexa", True) and phases[-1] == ("released euroqexa", True)
    assert set(phases[1:-1]) == {("say", False)}
    assert on_mine()


def test_the_record_is_closed_while_the_lock_is_held_and_before_the_handlers_are_set_back(
        tmp_path, places, clock, monkeypatch):
    own_handlers()
    phases, close = [], record.Record.close

    def noted(self):
        phases.append(("closed", on_mine()))
        close(self)

    monkeypatch.setattr(record.Record, "close", noted)
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1, take_lock=lock_of_test(phases)) == 0
    assert phases == [("taken euroqexa", True), ("closed", False), ("released euroqexa", True)]


@pytest.mark.parametrize("stage, word", [({"resume": True, "max_order": 2, "rules_file": B}, "--new-rules"),
                                         ({"max_order": 1}, "--new-run")], ids=["a rules file", "an earlier record"])
def test_a_call_refused_while_its_record_is_opened_leaves_send_with_the_lock_released_and_the_handlers_back(
        tmp_path, places, clock, monkeypatch, stage, word):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    own_handlers()
    phases, read_bytes = [], Path.read_bytes

    def noted(path):
        if path == rec:
            phases.append(("read", on_mine()))
        return read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", noted)
    stage = {**stage, "resume": rec} if "resume" in stage else stage
    with pytest.raises(runner.Refused, match=word):
        send(m, FakeSite(), places, clock, take_lock=lock_of_test(phases), **stage)
    assert phases[0] == ("taken euroqexa", True) and phases[-1] == ("released euroqexa", True)
    assert set(phases[1:-1]) == {("read", False)}
    assert on_mine()


def test_a_lock_that_cannot_be_taken_sets_no_handler_and_opens_no_record(tmp_path, places, clock, monkeypatch):
    def refuse(site):
        raise LockRefused("another live call holds the lock")

    own_handlers()
    m, site, set_to = write_manifest(tmp_path / "m"), FakeSite(), []
    with monkeypatch.context() as patch:
        patch.setattr(signal, "signal", lambda number, handler: set_to.append(number))
        with pytest.raises(LockRefused):
            send(m, site, places, clock, max_order=1, take_lock=refuse)
    assert set_to == [] and site.calls == [] and not places.records.exists()


def test_the_holder_file_is_on_disk_from_the_opening_of_the_record_to_the_end_of_the_call(tmp_path, places, clock):
    holder, seen = places.state / "euroqexa.holder", []
    assert live(write_manifest(tmp_path / "m"), FakeSite(), places, clock, lambda text: seen.append(holder.exists()),
                max_order=1) == 0
    assert set(seen) == {True} and not holder.exists()


@pytest.mark.parametrize("number, other", [(signal.SIGHUP, signal.SIGTERM), (signal.SIGTERM, signal.SIGHUP)],
                         ids=["SIGHUP", "SIGTERM"])
def test_a_signal_set_to_ignore_stays_ignored_during_the_call_and_after_it(tmp_path, places, clock, number, other):
    signal.signal(number, signal.SIG_IGN)
    signal.signal(other, mine)
    seen = []

    def hit():
        signal.raise_signal(number)
        return STATE("COMPLETED", final=True, ok=True)

    def say(text):
        seen.append((signal.getsignal(number), signal.getsignal(other)))

    m = write_manifest(tmp_path / "m")
    assert live(m, FakeSite(states={"J-1": [hit]}), places, clock, say, max_order=1) == 0
    ignored, caught = zip(*seen, strict=True)
    assert set(ignored) == {signal.SIG_IGN} and mine not in caught
    assert signal.getsignal(number) == signal.SIG_IGN and signal.getsignal(other) is mine


@pytest.mark.parametrize("number, name", NAMES, ids=[name for _, name in NAMES])
def test_a_caught_signal_raises_keyboard_interrupt_with_its_name_and_restore_sets_the_handler_back(number, name):
    own_handlers()
    earlier = catch_kills()
    assert not on_mine()
    with pytest.raises(KeyboardInterrupt) as caught:
        signal.raise_signal(number)
    assert caught.value.args == (name,)
    restore(earlier)
    assert on_mine()


def test_an_earlier_handler_of_none_is_restored_as_the_default(monkeypatch):
    own_handlers()
    with monkeypatch.context() as patch:
        patch.setattr(signal, "getsignal", lambda number: None)
        restore(catch_kills())
    assert handlers() == [signal.SIG_DFL, signal.SIG_DFL]


@pytest.mark.parametrize("number, name", NAMES, ids=[name for _, name in NAMES])
def test_the_name_of_the_signal_reaches_the_stop_line_and_the_text_of_the_call(tmp_path, places, clock, number, name):
    own_handlers()

    def hit():
        signal.raise_signal(number)
        return STATE()

    m, said = write_manifest(tmp_path / "m"), []
    assert live(m, FakeSite(states={"J-1": [hit]}), places, clock, said.append, max_order=1) == 130
    rec = records_of(places)[0]
    assert events(rec, "stop")[-1]["reason"] == f"interrupted by {name}; nothing was cancelled"
    assert (f"\nInterrupted by {name}. Nothing was cancelled. Collect with: qdevices send {quoted(m)} --live "
            f"--resume {quoted(rec)}") in said
    assert on_mine()


def test_another_record_with_seconds_too_large_for_a_float_counts_them_at_the_job_time_limit(
        tmp_path, places, clock, monkeypatch):
    # fault 15, fixed: the send ended after the start line, with no stop line
    other = another_record(places, 10 ** 400)
    before = other.read_bytes()
    own_handlers()
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1) == 0
    new = next(path for path in records_of(places) if path != other)
    end = lines_of(new)[-1]
    assert lines_of(new)[0]["event"] == "start" and end["event"] == "end"
    assert end["used_seconds"] == 101.5           # the other result at job_seconds_limit, 100 s, and this one
    assert other.read_bytes() == before
    assert not (places.state / "euroqexa.holder").exists() and on_mine()


@pytest.mark.parametrize("stage", [{}, {"max_order": 2}], ids=["collects", "sends"])
def test_a_resume_whose_earlier_lines_hold_an_event_that_is_a_list_passes_that_line_over(
        tmp_path, places, clock, monkeypatch, stage):
    # fault 15, fixed: the send ended after its resume line, with no stop line
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(), places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    with open(rec, "a", encoding="utf-8") as fh:
        fh.write('{"event": ["result"], "order": 1}\n')
    before = rec.read_bytes()
    own_handlers()
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, **stage) == 0
    assert rec.read_bytes().startswith(before)
    assert lines_of(rec)[-1]["event"] == "end"
    assert [c for c in site.calls if c[0] == "submit"] == ([("submit", 2)] if stage else [])    # never order 1
    assert not (places.state / "euroqexa.holder").exists() and on_mine()


def test_an_interrupt_at_the_say_of_the_new_record_writes_its_stop_line_and_ends_in_130(
        tmp_path, places, clock, monkeypatch):
    # fault 15, fixed: the loop was not yet there to write a stop line
    said = []

    def say(text):
        said.append(text)
        if text.startswith("Record: "):
            raise KeyboardInterrupt()

    own_handlers()
    made, site = records_made(monkeypatch), FakeSite()
    assert live(write_manifest(tmp_path / "m"), site, places, clock, say, max_order=1) == 130
    assert said[-1].startswith("\nInterrupted by Ctrl-C. Nothing was cancelled.")
    lines = lines_of(records_of(places)[0])
    assert [line["event"] for line in lines] == ["start", "stop"] and lines[-1]["kind"] == "interrupt"
    assert site.calls == [] and all(rec._fh.closed for rec in made)
    assert not (places.state / "euroqexa.holder").exists() and on_mine()


def test_a_rules_file_whose_read_fails_is_refused_with_the_kind_of_the_error(tmp_path, monkeypatch):
    path = tmp_path / "rules.py"
    path.write_text("# the rules of an experiment\n")
    read_bytes = Path.read_bytes

    def denied(self):
        if self == path:
            raise PermissionError(13, "Permission denied")
        return read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", denied)
    with pytest.raises(runner.Refused) as refused:
        load_rules(path)
    assert type(refused.value).__name__ == "RuleFileError"
    assert str(refused.value) == f"the rules file {path} cannot be read: PermissionError"
