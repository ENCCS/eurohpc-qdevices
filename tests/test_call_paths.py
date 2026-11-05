"""What a call writes and says at the paths no other test reaches, and at each point where it can end."""

import signal

import pytest
from fakes import STATE, FakeSite, cfg, events, lines_of, records_of, send, write_manifest
from fakes.older import main
from runner_calls import ctrl_c

from qdevices import record, runner
from qdevices.ledger import Ledger
from qdevices.screen import quoted
from qdevices.sites.base import NoAnswer, SiteError

BEFORE_SEND = ["start", "read", *["rule"] * 7]        # a record up to the line before its first job request
TO_RESULT = ["submitting", "submitted", "status", "result", "rule", "rule"]       # one order that ends well
KILLS = (signal.SIGTERM, signal.SIGHUP)
INTERRUPTED = "interrupted by Ctrl-C; nothing was cancelled"
UNDER_WAY = "Under way at the stop: order 1 (J1), job J-1."
COLLECT_NOTE = "Collect it soon."                     # of a fake site, to see when a call prints it
FULL_DISK = "an error of the program: OSError: [Errno 28] No space left on device"
VLQ_HEAD = ["event", "utc", "app", "site", "machine", "project", "lexis_project", "resource"]
PICK_3 = {"before_job": lambda job, state: {"rule": "pick", "passed": True, "skip": [3]}}


def live(m, site, places, clock, say, **kw) -> int:
    """One live call that says each line through `say`."""
    return runner.send(m, site, cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="host-a", say=say, **kw)


def events_of(rec) -> list:
    """The event of each line of a record."""
    return [line["event"] for line in lines_of(rec)]


def whole(event: str, clock, **fields) -> list[tuple]:
    """The keys and values of a line of a Euro-Q-Exa record, in order, written at the time of the clock."""
    base = {"app": "qdevices", "site": "euroqexa", "machine": "M1", "project": "TEST-PROJECT"}
    return [("event", event), ("utc", clock.utc().isoformat()), *base.items(), *fields.items()]


def collect_with(m, rec) -> str:
    """What a call prints at Ctrl-C, with no rules file."""
    return ("\nInterrupted by Ctrl-C. Nothing was cancelled. Collect with: qdevices send "
            f"{quoted(m)} --live --resume {quoted(rec)}")


def saying(said: list, at: str, error: BaseException):
    """A say that keeps each line, and raises `error` once, at the first line that starts with `at`."""
    hit = []

    def say(text):
        said.append(text)
        if text.startswith(at) and not hit:
            hit.append(text)
            raise error

    return say


def noting(places, seen: list):
    """A say that keeps each line with the event of the last line of the record on disk at that moment."""
    def say(text):
        seen.append((text, record.RecordLines.read(records_of(places)[-1]).events[-1]["event"]))

    return say


def on_disk_at(seen: list, lead: str) -> list:
    """The event of the last line on disk at each say that starts with `lead`."""
    return [event for text, event in seen if text.startswith(lead)]


def no_space() -> OSError:
    """The error of a full disk."""
    return OSError(28, "No space left on device")


def fail_once(monkeypatch, failing: str, error: BaseException) -> None:
    """Record.write raises `error` once, at the first line of the event `failing`, before anything of it is written."""
    write, hit = record.Record.write, []

    def once(self, event, **fields):
        if event == failing and not hit:
            hit.append(event)
            raise error
        return write(self, event, **fields)

    monkeypatch.setattr(record.Record, "write", once)


def fail_always(monkeypatch, *failing: str) -> None:
    """Record.write raises OSError at each line of these events, before anything of it is written."""
    write = record.Record.write

    def denied(self, event, **fields):
        if event in failing:
            raise no_space()
        return write(self, event, **fields)

    monkeypatch.setattr(record.Record, "write", denied)


def records_made(monkeypatch) -> list:
    """Each Record made from here on, to see that it is closed."""
    init, made = record.Record.__init__, []

    def keep(self, *args, **kw):
        made.append(self)
        init(self, *args, **kw)

    monkeypatch.setattr(record.Record, "__init__", keep)
    return made


def closed(made: list) -> list[bool]:
    """Whether each Record made is closed."""
    return [rec._fh.closed for rec in made]


def mine(signum, frame):
    """A handler of the test, to tell from those of the app."""


def own_handlers() -> None:
    """Both signals set to the handler of the test; the fixture of conftest.py sets them back."""
    for number in KILLS:
        signal.signal(number, mine)


def handlers() -> list:
    """What both signals are set to now."""
    return [signal.getsignal(number) for number in KILLS]


def interrupting(*args):
    """A rule of a user that is Ctrl-C."""
    raise KeyboardInterrupt()


def with_a_step_note() -> FakeSite:
    """A site whose job request writes a note that holds no id."""
    return FakeSite(submits={1: ("steps", ("id", "J-1"), [("uploaded", {})])})


def with_an_init_note() -> FakeSite:
    """A VLQ-shaped site whose work before the job writes a note that holds no id."""
    site = FakeSite("vlq", seconds_left=3600)
    site.prepare = lambda job, note: note("init_submitting")
    return site


def with_an_init_job(**answers) -> FakeSite:
    """A VLQ-shaped site whose work before the job makes the init job 5 and ends well."""
    site = FakeSite("vlq", seconds_left=3600, **answers)
    site.prepare = lambda job, note: note("init_created", init_job=5)
    return site


def made_then(job, action) -> FakeSite:
    """A VLQ-shaped site whose job request makes this job, then ends in `action`."""
    return FakeSite("vlq", seconds_left=3600, submits={1: ("steps", action, [("created", {"job": job})])})


def configuring() -> FakeSite:
    """A VLQ-shaped site that shows the job 7 as still being configured."""
    return FakeSite("vlq", seconds_left=3600, states={7: [STATE("Configuring", configuring=True)]})


def created_job(tmp_path, places, clock) -> tuple:
    """A record of a VLQ-shaped order whose job 7 was made and never submitted: the manifest and the record."""
    m = write_manifest(tmp_path / "m", site="vlq")
    assert send(m, made_then(7, ("interrupt",)), places, clock, max_order=1) == 130
    return m, records_of(places)[0]


def left_open(tmp_path, places, clock) -> tuple:
    """A record whose order 1 is still running at wait_seconds: the manifest and the record."""
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(states={"J-1": [STATE()]}), places, clock, max_order=1) == 2
    return m, records_of(places)[0]


def test_an_interrupt_at_the_say_of_the_sent_job_writes_the_submitted_line_then_the_stop_and_leaves_the_order_open(
        tmp_path, places, clock):
    m, site, said = write_manifest(tmp_path / "m"), FakeSite(), []
    assert live(m, site, places, clock, saying(said, "  job J-1 sent", KeyboardInterrupt()), max_order=1) == 130
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting", "submitted", "stop"]
    submitted, stop = lines_of(rec)[-2:]
    assert list(submitted.items()) == whole("submitted", clock, order=1, name="J1", id="J-1",
                                            submitted_utc=clock.utc().isoformat())
    assert list(stop.items()) == whole("stop", clock, kind="interrupt", reason=INTERRUPTED, order=1, name="J1",
                                       phase="submit", id="J-1")
    assert site.calls == [("read",), ("prepare", 1), ("submit", 1)]
    assert said[-2:] == [collect_with(m, rec), UNDER_WAY]
    assert Ledger(lines_of(rec)).orders[1].status == "open"
    later = FakeSite()
    assert send(m, later, places, clock, resume=rec) == 0
    assert later.calls == [("status", "J-1"), ("result", "J-1")]


def test_an_error_at_the_say_of_the_sent_job_writes_the_submitted_line_then_the_stop_and_warns(
        tmp_path, places, clock, capsys):
    say = saying([], "  job J-1 sent", ValueError("a fault of the say"))
    assert live(write_manifest(tmp_path / "m"), FakeSite(), places, clock, say, max_order=1) == 3
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting", "submitted", "stop"]
    assert list(lines_of(rec)[-1].items()) == whole(
        "stop", clock, kind="error", reason="an error of the program: ValueError: a fault of the say", order=1,
        name="J1", phase="submit", id="J-1")
    err = capsys.readouterr().err
    assert ("FAILED: an error of the program in a live call. A job may be at the site: read the record "
            f"{rec} before the next step.") in err
    assert UNDER_WAY in err


@pytest.mark.parametrize("error, code, kind", [(KeyboardInterrupt(), 130, "interrupt"), (no_space(), 3, "error")],
                         ids=["interrupt", "error"])
def test_a_submitted_line_cut_in_its_write_is_written_once_on_the_way_out_before_the_stop(
        tmp_path, places, clock, monkeypatch, error, code, kind):
    fail_once(monkeypatch, "submitted", error)
    site = FakeSite()
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == code
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting", "submitted", "stop"]
    submitted, stop = lines_of(rec)[-2:]
    assert (submitted["id"], submitted["submitted_utc"]) == ("J-1", clock.utc().isoformat())
    assert (stop["kind"], stop["phase"], stop["id"]) == (kind, "submit", "J-1")
    assert ("status", "J-1") not in site.calls


def test_every_write_failing_from_the_submitted_line_on_gives_exit_3_and_both_warnings_and_closes_the_record(
        tmp_path, places, clock, monkeypatch, capsys):
    fail_always(monkeypatch, "submitted", "stop")
    made, site = records_made(monkeypatch), FakeSite()
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 3
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting"]
    err = capsys.readouterr().err
    assert "FAILED: an error of the program" in err and UNDER_WAY in err
    assert closed(made) == [True]
    assert Ledger(lines_of(rec)).orders[1].status == "lost"
    assert ("status", "J-1") not in site.calls


def test_after_an_error_of_the_program_a_submitted_line_whose_write_fails_is_written_once_more_before_the_close(
        tmp_path, places, clock, monkeypatch):
    fail_once(monkeypatch, "submitted", no_space())
    made = records_made(monkeypatch)
    say = saying([], "  job J-1 sent", ValueError("a fault of the say"))
    assert live(write_manifest(tmp_path / "m"), FakeSite(), places, clock, say, max_order=1) == 3
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting", "stop", "submitted"]     # the stop line is tried
    assert closed(made) == [True]
    assert Ledger(lines_of(rec)).orders[1].status == "open"


def test_after_an_interrupt_a_submitted_line_whose_write_fails_is_written_once_more_before_the_close_and_ends_in_130(
        tmp_path, places, clock, monkeypatch):
    fail_once(monkeypatch, "submitted", no_space())
    made = records_made(monkeypatch)
    say = saying([], "  job J-1 sent", KeyboardInterrupt())
    assert live(write_manifest(tmp_path / "m"), FakeSite(), places, clock, say, max_order=1) == 130
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting", "stop", "submitted"]
    assert closed(made) == [True]
    assert Ledger(lines_of(rec)).orders[1].status == "open"


def test_a_stop_line_that_cannot_be_written_after_an_error_of_the_program_still_warns(
        tmp_path, places, clock, monkeypatch, capsys):
    fail_always(monkeypatch, "stop")
    say = saying([], "  job J-1 sent", ValueError("a fault of the say"))
    assert live(write_manifest(tmp_path / "m"), FakeSite(), places, clock, say, max_order=1) == 3
    assert events_of(records_of(places)[0]) == [*BEFORE_SEND, "submitting", "submitted"]
    err = capsys.readouterr().err
    assert "FAILED: an error of the program" in err and UNDER_WAY in err


def test_a_stop_line_that_cannot_be_written_after_an_interrupt_is_warned_and_ends_in_130_with_the_lock_back(
        tmp_path, places, clock, monkeypatch):
    own_handlers()
    fail_always(monkeypatch, "stop")
    made, said = records_made(monkeypatch), []
    site = FakeSite(states={"J-1": [ctrl_c]})
    assert live(write_manifest(tmp_path / "m"), site, places, clock, said.append, max_order=1) == 130
    assert events_of(records_of(places)[0]) == [*BEFORE_SEND, "submitting", "submitted"]
    assert not (places.state / "euroqexa.holder").exists()
    assert handlers() == [mine, mine]
    assert closed(made) == [True]
    assert [text for text in said if text.startswith("\nInterrupted by Ctrl-C")] and UNDER_WAY in said


def test_a_stop_whose_line_cannot_be_written_becomes_an_error_of_the_program_that_names_the_job(
        tmp_path, places, clock, monkeypatch):
    fail_once(monkeypatch, "stop", no_space())
    site, said = FakeSite(states={"J-1": [STATE()]}), []
    assert live(write_manifest(tmp_path / "m"), site, places, clock, said.append, max_order=1) == 3
    stop = lines_of(records_of(places)[0])[-1]
    assert (stop["event"], stop["kind"], stop["order"], stop["id"]) == ("stop", "error", 1, "J-1")
    assert not [text for text in said if text.startswith("STOP:")]


def test_an_interrupt_at_the_say_of_a_stop_writes_a_second_stop_line_and_ends_in_130(tmp_path, places, clock):
    site, say = FakeSite(states={"J-1": [STATE()]}), saying([], "STOP:", KeyboardInterrupt())
    assert live(write_manifest(tmp_path / "m"), site, places, clock, say, max_order=1) == 130
    assert [line["kind"] for line in events(records_of(places)[0], "stop")] == ["timeout", "interrupt"]


def test_logs_of_a_failed_job_that_cannot_be_read_are_empty_and_the_call_goes_on_to_the_rule_on_refusal(
        tmp_path, places, clock):
    def no_logs(job_id):
        raise SiteError("HTTP 500 to GET logs", status=500, step="logs")

    site = FakeSite(states={"J-1": [STATE("FAILED", final=True)]})
    site.logs = no_logs
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting", "submitted", "status", "failed", "rule", "stop"]
    failed, rule, stop = lines_of(rec)[-3:]
    assert list(failed.items()) == whole("failed", clock, order=1, name="J1", id="J-1", state="FAILED", logs={})
    assert (rule["point"], rule["rule"], rule["passed"]) == ("on_refusal", "refusal", False)
    assert (stop["kind"], stop["rule"]) == ("rule", "refusal")
    assert stop["reason"] == "rule refusal: order 1 (J1): failed: the job ended FAILED"


def test_a_missed_poll_writes_its_line_and_counts_on_and_only_a_read_that_answers_is_a_poll(tmp_path, places, clock):
    silent = NoAnswer("no answer to GET status: ConnectError", step="status")
    site = FakeSite(states={"J-1": [silent, STATE(), silent, STATE("COMPLETED", final=True, ok=True)]})
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    status = events(rec, "status")
    assert [(e.get("missed"), e.get("misses"), e.get("state"), e.get("poll")) for e in status] == [
        ("no answer", 1, None, None), (None, None, "RUNNING", 1), ("no answer", 2, None, None),
        (None, None, "COMPLETED", 2)]
    assert list(status[0].items())[6:] == [("order", 1), ("name", "J1"), ("id", "J-1"), ("missed", "no answer"),
                                           ("misses", 1), ("error", "no answer to GET status: ConnectError"),
                                           ("http_status", None), ("body", None), ("step", "status")]
    assert events(rec, "result")[0]["polls"] == 2


@pytest.mark.parametrize("resumed", [False, True], ids=["a first call", "a resume"])
def test_a_job_with_a_submitted_line_that_the_site_shows_as_configuring_is_polled_on(
        tmp_path, places, clock, resumed):
    site = FakeSite(states={"J-1": [STATE("Configuring", configuring=True), STATE("COMPLETED", final=True, ok=True)]})
    if resumed:
        m, rec = left_open(tmp_path, places, clock)
        assert send(m, site, places, clock, resume=rec) == 0
    else:
        assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 0
        rec = records_of(places)[0]
    assert [line["state"] for line in events(rec, "status")][-2:] == ["Configuring", "COMPLETED"]
    assert len(events(rec, "result")) == 1 and events(rec, "not_submitted") == []


def test_a_resume_of_an_id_from_resolve_at_a_wall_time_site_with_no_seconds_stops_at_job_time(tmp_path, places, clock):
    m = write_manifest(tmp_path / "m")
    assert send(m, FakeSite(submits={1: ("interrupt",)}), places, clock, max_order=1) == 130
    rec = records_of(places)[0]
    assert main(places, clock, "resolve", str(rec), "1", "--job", "J-found") == 0
    site, said = FakeSite(seconds_kind="wall"), []
    site.result = lambda job_id: {"counts": {"1": 10}}
    assert live(m, site, places, clock, said.append, resume=rec) == 2
    assert events_of(rec)[-6:] == ["resume", "status", "result", "rule", "rule", "stop"]
    lines = lines_of(rec)
    assert not [line for line in lines if line["event"] == "submitted"]
    assert list(lines[-4].items()) == whole(
        "result", clock, order=1, name="J1", id="J-found", shots=10, counts={"1": 10}, seconds=None,
        seconds_kind="wall", wall_seconds=None, published_seconds=None, polls=1, recovered=True)
    assert (lines[-2]["rule"], lines[-2]["passed"], lines[-2]["reason"]) == (
        "job_time", False, "the job has no measured time")
    assert list(lines[-1].items()) == whole("stop", clock, reason="rule job_time: the job has no measured time",
                                            kind="rule", rule="job_time", order=1)
    assert "  job J-found: result in the record" in said


def test_the_wall_seconds_start_before_the_job_request_and_the_submitted_time_is_read_after_it(tmp_path, places, clock):
    def slow(job, note, prepared=None):
        clock.t += 7
        return "J-1"

    site = FakeSite(seconds_kind="wall")
    site.submit = slow
    site.result = lambda job_id: {"counts": {"1": 10}}
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 0
    rec = records_of(places)[0]
    result = events(rec, "result")[0]
    assert (result["seconds"], result["wall_seconds"]) == (7.0, 7.0)
    assert events(rec, "submitting")[0]["utc"] == clock.start.isoformat()
    assert events(rec, "submitted")[0]["submitted_utc"] == clock.utc().isoformat()


@pytest.mark.parametrize("make, name, failing, phase, lines", [
    (with_a_step_note, "euroqexa", "step", "submit", [*BEFORE_SEND, "submitting", "stop"]),
    (with_an_init_note, "vlq", "init", "prepare", [*BEFORE_SEND, "stop"]),
], ids=["step", "init"])
def test_a_note_with_no_id_whose_write_fails_prints_no_record_write_failed(
        tmp_path, places, clock, monkeypatch, capsys, make, name, failing, phase, lines):
    fail_once(monkeypatch, failing, no_space())
    assert send(write_manifest(tmp_path / "m", site=name), make(), places, clock, max_order=1) == 3
    rec = records_of(places)[0]
    assert events_of(rec) == lines
    stop = lines_of(rec)[-1]
    assert (stop["kind"], stop["order"], stop["phase"]) == ("error", 1, phase)
    assert stop["reason"] == FULL_DISK
    err = capsys.readouterr().err
    assert "FAILED: an error of the program" in err
    assert "RECORD WRITE FAILED" not in err and "Under way" not in err


def test_a_note_of_an_init_job_whose_write_fails_shows_the_init_job(tmp_path, places, clock, monkeypatch, capsys):
    fail_once(monkeypatch, "init", no_space())
    assert send(write_manifest(tmp_path / "m", site="vlq"), with_an_init_job(), places, clock, max_order=1) == 3
    err = capsys.readouterr().err
    assert ("RECORD WRITE FAILED (OSError): order 1 (J1), init job 5: its init_created line may not be in the record; "
            "write this id down") in err
    assert "Under way at the stop: order 1 (J1), init job 5." in err
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "stop"]
    stop = lines_of(rec)[-1]
    assert (stop["kind"], stop["phase"], stop["init_job"]) == ("error", "prepare", 5)


def test_an_id_of_0_from_the_job_request_is_an_id_in_the_wait_and_on_a_resume(tmp_path, places, clock):
    m, said = write_manifest(tmp_path / "m"), []
    site = FakeSite(submits={1: ("id", 0)}, states={0: [ctrl_c]})
    site.collect_note = COLLECT_NOTE
    assert live(m, site, places, clock, said.append, max_order=1) == 130
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting", "submitted", "stop"]
    submitted, stop = lines_of(rec)[-2:]
    assert submitted["id"] == 0 and "  job 0 sent" in said
    assert list(stop.items()) == whole("stop", clock, kind="interrupt", reason=INTERRUPTED, order=1, name="J1", id=0)
    assert said[-2:] == ["Under way at the stop: order 1 (J1), job 0.", COLLECT_NOTE]
    assert Ledger(lines_of(rec)).orders[1].status == "open"
    later = FakeSite()
    assert send(m, later, places, clock, resume=rec) == 0
    assert later.calls == [("status", 0), ("result", 0)]


def test_an_interrupt_after_a_note_of_the_job_0_names_the_job(tmp_path, places, clock):
    site, said = made_then(0, ("interrupt",)), []
    assert live(write_manifest(tmp_path / "m", site="vlq"), site, places, clock, said.append, max_order=1) == 130
    assert lines_of(records_of(places)[0])[-1]["id"] == 0
    assert said[-1] == "Under way at the stop: order 1 (J1), job 0."


def test_a_job_request_with_no_good_answer_after_a_note_of_the_job_0_says_that_the_job_was_made(
        tmp_path, places, clock):
    m = write_manifest(tmp_path / "m", site="vlq")
    assert send(m, made_then(0, ("unknown", 503)), places, clock, max_order=1) == 2
    stop = lines_of(records_of(places)[0])[-1]
    assert stop["id"] == 0
    assert stop["reason"].endswith("The order is never sent again: job 0 was made; a resume reads its state")


def test_an_interrupt_after_a_note_of_the_init_job_0_names_it(tmp_path, places, clock):
    def prepare(job, note):
        note("init_created", init_job=0)
        raise KeyboardInterrupt()

    site, said = FakeSite("vlq", seconds_left=3600), []
    site.prepare = prepare
    assert live(write_manifest(tmp_path / "m", site="vlq"), site, places, clock, said.append, max_order=1) == 130
    assert lines_of(records_of(places)[0])[-1]["init_job"] == 0
    assert said[-1] == "Under way at the stop: order 1 (J1), init job 0."


@pytest.mark.parametrize("made", [7, 0])
def test_a_refusal_after_a_note_keeps_the_job_on_its_line_and_for_the_rule(tmp_path, places, clock, made):
    given = []
    user = {"on_refusal": lambda job, info: given.append(info) or {"rule": "mine", "passed": True}}
    m = write_manifest(tmp_path / "m", site="vlq")
    assert send(m, made_then(made, ("refuse", 400)), places, clock, max_order=1, user_rules=user) == 0
    assert events(records_of(places)[0], "refused")[0]["id"] == made
    assert given[0]["id"] == made


@pytest.mark.parametrize("point, answers, lines, status", [
    ("before_call", {}, ["start", "read", "stop"], "unsent"),
    ("before_job", {}, ["start", "read", "rule", "rule", "stop"], "unsent"),
    ("after_result", {}, [*BEFORE_SEND, "submitting", "submitted", "status", "result", "stop"], "final"),
    ("on_refusal", {"submits": {1: ("refuse", 400)}}, [*BEFORE_SEND, "submitting", "refused", "stop"], "final"),
    ("on_refusal", {"states": {"J-1": [STATE("FAILED", final=True)]}},
     [*BEFORE_SEND, "submitting", "submitted", "status", "failed", "stop"], "final"),
], ids=["before_call", "before_job", "after_result", "on_refusal of a refused job", "on_refusal of a failed job"])
def test_an_interrupt_in_a_rule_leaves_nothing_under_way_on_the_stop_line_or_on_the_screen(
        tmp_path, places, clock, point, answers, lines, status):
    site, said = FakeSite(**answers), []
    site.collect_note = COLLECT_NOTE
    m = write_manifest(tmp_path / "m")
    assert live(m, site, places, clock, said.append, max_order=1, user_rules={point: interrupting}) == 130
    rec = records_of(places)[0]
    assert events_of(rec) == lines
    assert list(lines_of(rec)[-1].items()) == whole("stop", clock, kind="interrupt", reason=INTERRUPTED)
    assert Ledger(lines_of(rec)).status(1) == status
    assert not [text for text in said if text.startswith("Under way")]
    assert said[-1] == collect_with(m, rec) and COLLECT_NOTE not in said


@pytest.mark.parametrize("event, answers, text", [
    ("result", {}, "  job J-1: result in the record, 1.500 s"),
    ("failed", {"states": {"J-1": [STATE("FAILED", final=True)]}}, "  job J-1: ended FAILED"),
    ("refused", {"submits": {1: ("refuse", 400)}}, "  refused by the site: HTTP 400"),
], ids=["result", "failed", "refused"])
def test_an_interrupt_at_the_say_of_a_final_line_leaves_nothing_under_way(
        tmp_path, places, clock, event, answers, text):
    said = []
    say = saying(said, text, KeyboardInterrupt())
    assert live(write_manifest(tmp_path / "m"), FakeSite(**answers), places, clock, say, max_order=1) == 130
    rec = records_of(places)[0]
    assert events_of(rec)[-2:] == [event, "stop"]
    assert list(lines_of(rec)[-1].items()) == whole("stop", clock, kind="interrupt", reason=INTERRUPTED)
    assert Ledger(lines_of(rec)).status(1) == "final"
    assert not [line for line in said if line.startswith("Under way")]


@pytest.mark.parametrize("at, user", [("  job 7: not submitted, final", None), (None, {"on_refusal": interrupting})],
                         ids=["at its say", "in the rule"])
def test_an_interrupt_after_a_not_submitted_line_leaves_nothing_under_way(tmp_path, places, clock, at, user):
    m, rec = created_job(tmp_path, places, clock)
    said = []
    say = saying(said, at, KeyboardInterrupt()) if at else said.append
    assert live(m, configuring(), places, clock, say, resume=rec, user_rules=user) == 130
    assert events_of(rec)[-2:] == ["not_submitted", "stop"]
    stop = lines_of(rec)[-1]
    assert list(stop) == [*VLQ_HEAD, "kind", "reason"] and stop["reason"] == INTERRUPTED
    assert Ledger(lines_of(rec)).status(1) == "final"
    assert not [line for line in said if line.startswith("Under way")]


def test_a_refused_line_that_cannot_be_written_is_not_said_and_leaves_the_order_lost(
        tmp_path, places, clock, monkeypatch):
    fail_once(monkeypatch, "refused", no_space())
    site, said = FakeSite(submits={1: ("refuse", 400)}), []
    assert live(write_manifest(tmp_path / "m"), site, places, clock, said.append, max_order=1) == 3
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "submitting", "stop"]
    assert list(lines_of(rec)[-1].items()) == whole("stop", clock, kind="error", reason=FULL_DISK, order=1, name="J1",
                                                    phase="submit")
    assert not [line for line in said if line.startswith("  refused")]
    assert Ledger(lines_of(rec)).status(1) == "lost"


def test_a_not_submitted_line_that_cannot_be_written_is_not_said_and_names_the_job(
        tmp_path, places, clock, monkeypatch, capsys):
    m, rec = created_job(tmp_path, places, clock)
    fail_once(monkeypatch, "not_submitted", no_space())
    said = []
    assert live(m, configuring(), places, clock, said.append, resume=rec) == 3
    assert events(rec, "not_submitted") == []
    stop = lines_of(rec)[-1]
    assert (stop["kind"], stop["reason"], stop["order"], stop["name"], stop["id"]) == ("error", FULL_DISK, 1, "J1", 7)
    assert not [line for line in said if "not submitted, final" in line]
    assert "Under way at the stop: order 1 (J1), job 7." in capsys.readouterr().err
    assert Ledger(lines_of(rec)).status(1) == "open"


def test_an_interrupt_in_prepare_after_the_note_of_an_init_job_names_the_init_job(tmp_path, places, clock):
    def prepare(job, note):
        note("init_created", init_job=5)
        raise KeyboardInterrupt()

    site, said = FakeSite("vlq", seconds_left=3600), []
    site.prepare = prepare
    assert live(write_manifest(tmp_path / "m", site="vlq"), site, places, clock, said.append, max_order=1) == 130
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "init", "stop"]
    stop = lines_of(rec)[-1]
    assert list(stop) == [*VLQ_HEAD, "kind", "reason", "order", "name", "phase", "init_job"]
    assert (stop["order"], stop["name"], stop["phase"], stop["init_job"]) == (1, "J1", "prepare", 5)
    assert said[-1] == "Under way at the stop: order 1 (J1), init job 5."


def test_an_interrupt_with_a_job_and_an_init_job_in_hand_names_both(tmp_path, places, clock):
    def prepare(job, note):
        note("init_created", init_job=5)
        note("created", job=7)
        raise KeyboardInterrupt()

    site, said = FakeSite("vlq", seconds_left=3600), []
    site.prepare = prepare
    assert live(write_manifest(tmp_path / "m", site="vlq"), site, places, clock, said.append, max_order=1) == 130
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, "init", "step", "stop"]
    assert list(lines_of(rec)[-1])[-5:] == ["order", "name", "phase", "init_job", "id"]
    assert said[-1] == "Under way at the stop: order 1 (J1), job 7 and init job 5."


@pytest.mark.parametrize("action, keys, named", [
    (("interrupt",), ["order", "name", "phase"], []),
    (("steps", ("interrupt",), [("created", {"job": 7})]), ["order", "name", "phase", "id"],
     ["Under way at the stop: order 1 (J1), job 7."]),
], ids=["before a job is made", "after a job is made"])
def test_the_init_job_leaves_what_is_under_way_once_the_job_request_starts(
        tmp_path, places, clock, action, keys, named):
    site, said = with_an_init_job(submits={1: action}), []
    assert live(write_manifest(tmp_path / "m", site="vlq"), site, places, clock, said.append, max_order=1) == 130
    stop = lines_of(records_of(places)[0])[-1]
    assert list(stop) == [*VLQ_HEAD, "kind", "reason", *keys]
    assert stop["phase"] == "submit"
    assert [text for text in said if text.startswith("Under way")] == named


@pytest.mark.parametrize("answers, first", [
    ({"states": {"J-1": [STATE("FAILED", final=True)]}}, ["submitting", "submitted", "status", "failed", "rule"]),
    ({"submits": {1: ("refuse", 400)}}, ["submitting", "refused", "rule"]),
], ids=["failed", "refused"])
def test_a_users_on_refusal_that_passes_lets_the_call_send_the_next_order(tmp_path, places, clock, answers, first):
    user = {"on_refusal": lambda job, info: {"rule": "go_on", "passed": True}}
    site = FakeSite(**answers)
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=2, user_rules=user) == 0
    rec = records_of(places)[0]
    assert events_of(rec) == [*BEFORE_SEND, *first, *["rule"] * 5, *TO_RESULT, "end"]
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 1), ("submit", 2)]
    assert lines_of(rec)[-1]["left"] == [3]


def test_the_machine_is_read_once_in_a_call_that_sends_two_orders(tmp_path, places, clock):
    site = FakeSite()
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=2) == 0
    assert site.calls[0] == ("read",) and site.calls.count(("read",)) == 1
    assert events_of(records_of(places)[0]).count("read") == 1


def test_a_resume_that_only_collects_does_not_read_the_machine(tmp_path, places, clock):
    m, rec = left_open(tmp_path, places, clock)
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec) == 0
    assert site.calls == [("status", "J-1"), ("result", "J-1")]
    assert events_of(rec).count("read") == 1                  # of the first call


def test_a_resume_that_goes_on_reads_the_machine_once_after_it_has_collected(tmp_path, places, clock):
    m, rec = left_open(tmp_path, places, clock)
    site = FakeSite()
    assert send(m, site, places, clock, resume=rec, max_order=2) == 0
    assert site.calls == [("status", "J-1"), ("result", "J-1"), ("read",), ("prepare", 2), ("submit", 2),
                          ("status", "J-2"), ("result", "J-2")]


@pytest.mark.parametrize("answers, user, lines", [
    ({"read": {"machine": "M1", "online": False}}, None, ["start", "read", "rule", "rule", "stop"]),
    ({}, {"before_call": lambda read: {"rule": "mine", "passed": False, "reason": "not today"}},
     ["start", "read", "rule", "rule", "rule", "stop"]),
], ids=["generic", "user"])
def test_a_stop_in_the_rules_before_call_sends_nothing_and_writes_no_submitting(
        tmp_path, places, clock, answers, user, lines):
    site = FakeSite(**answers)
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1, user_rules=user) == 2
    assert events_of(records_of(places)[0]) == lines
    assert site.calls == [("read",)]


@pytest.mark.parametrize("answers, jobs, kind", [
    ({"max_shots": 200}, (("J1", 300),), "rule"),
    ({"states": {"J-1": [STATE()]}}, (("J1", 10),), "timeout"),
], ids=["rule", "timeout"])
def test_a_stop_leaves_no_end_line_and_closes_the_record(tmp_path, places, clock, monkeypatch, answers, jobs, kind):
    made = records_made(monkeypatch)
    assert send(write_manifest(tmp_path / "m", jobs=jobs), FakeSite(**answers), places, clock, max_order=1) == 2
    rec = records_of(places)[0]
    assert "end" not in events_of(rec)
    assert (lines_of(rec)[-1]["event"], lines_of(rec)[-1]["kind"]) == ("stop", kind)
    assert closed(made) == [True]


def test_an_end_line_that_cannot_be_written_is_an_error_of_the_program(tmp_path, places, clock, monkeypatch):
    fail_once(monkeypatch, "end", no_space())
    assert send(write_manifest(tmp_path / "m"), FakeSite(), places, clock, max_order=1) == 3
    rec = records_of(places)[0]
    assert "end" not in events_of(rec)
    assert list(lines_of(rec)[-1].items()) == whole("stop", clock, kind="error", reason=FULL_DISK)


def test_an_interrupt_at_the_say_of_the_end_line_writes_a_stop_line_after_it(tmp_path, places, clock):
    said = []
    say = saying(said, "End:", KeyboardInterrupt())
    assert live(write_manifest(tmp_path / "m"), FakeSite(), places, clock, say, max_order=1) == 130
    assert events_of(records_of(places)[0])[-2:] == ["end", "stop"]
    assert not [text for text in said if text.startswith("Go on with")]


@pytest.mark.parametrize("answers, user, lead, event", [
    ({}, None, "Record:", "start"),
    ({}, None, "  rule machine:", "rule"),
    ({}, None, "  job J-1 sent", "submitting"),           # before its submitted line
    ({}, None, "  job J-1: result", "result"),
    ({"states": {"J-1": [STATE("FAILED", final=True)]}}, None, "  job J-1: ended", "failed"),
    ({"submits": {1: ("refuse", 400)}}, None, "  refused by the site", "refused"),
    ({}, None, "End:", "end"),
    ({"max_shots": 5}, None, "STOP:", "stop"),
    ({"states": {"J-1": [ctrl_c]}}, None, "\nInterrupted", "stop"),
    ({}, PICK_3, "  SKIP:", "skip"),
], ids=["the record", "a rule", "the job sent", "a result", "a failed job", "a refusal", "the end", "a stop",
        "an interrupt", "a skip"])
def test_what_is_on_disk_at_each_say_of_a_call(tmp_path, places, clock, answers, user, lead, event):
    seen = []
    say = noting(places, seen)
    live(write_manifest(tmp_path / "m"), FakeSite(**answers), places, clock, say, max_order=1, user_rules=user)
    assert on_disk_at(seen, lead) == [event]


def test_the_note_of_a_read_comes_after_the_read_line(tmp_path, places, clock):
    site, seen = FakeSite(), []
    site.notes = lambda job, read: ["look here"]
    live(write_manifest(tmp_path / "m"), site, places, clock, noting(places, seen), max_order=1)
    assert on_disk_at(seen, "  NOTE: order 1 (J1): look here") == ["read"]


def test_the_note_of_the_table_comes_after_its_init_line(tmp_path, places, clock):
    site, seen = FakeSite("vlq", seconds_left=3600), []
    site.prepare = lambda job, note: note("init_done", table_note="look here")
    live(write_manifest(tmp_path / "m", site="vlq"), site, places, clock, noting(places, seen), max_order=1)
    assert on_disk_at(seen, "  NOTE: order 1 (J1): look here") == ["init"]


def test_the_say_of_a_not_submitted_line_comes_after_it(tmp_path, places, clock):
    m, rec = created_job(tmp_path, places, clock)
    seen = []
    live(m, configuring(), places, clock, noting(places, seen), resume=rec)
    assert on_disk_at(seen, "  job 7: not submitted") == ["not_submitted"]
