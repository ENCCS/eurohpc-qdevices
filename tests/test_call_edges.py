"""What a call writes and says at the edges of a wait and of a final line that the other guards leave open."""

from fakes import STATE, FakeSite, cfg, lines_of, records_of, write_manifest

from qdevices import runner

INTERRUPTED = "interrupted by Ctrl-C; nothing was cancelled"
HEAD = ("event", "utc", "app", "site", "machine", "project", "lexis_project", "resource")    # of every line


def live(m, site, places, clock, said: list, **kw) -> int:
    """One live call of the first order that keeps each line it says."""
    return runner.send(m, site, cfg=cfg(), places=places, clock=clock, sleep=clock.sleep, host="host-a",
                       say=said.append, max_order=1, **kw)


def events_of(rec) -> list:
    """The event of each line of a record."""
    return [line["event"] for line in lines_of(rec)]


def tail(rec, event: str) -> list[tuple]:
    """The keys and values of the last line of an event, without the head that every line has."""
    line = [line for line in lines_of(rec) if line["event"] == event][-1]
    return [(k, v) for k, v in line.items() if k not in HEAD]


def interrupt():
    """An answer of a state that is a Ctrl-C during the wait."""
    raise KeyboardInterrupt()


def test_a_result_whose_seconds_cannot_be_said_is_on_disk_before_the_error_of_the_program(
        tmp_path, places, clock, capsys):
    site, said = FakeSite(), []
    site.result = lambda job_id: {"counts": {"1": 10}, "seconds": "1.5"}
    assert live(write_manifest(tmp_path / "m"), site, places, clock, said) == 3
    rec = records_of(places)[0]
    assert events_of(rec)[-3:] == ["status", "result", "stop"]
    assert dict(tail(rec, "result"))["seconds"] == "1.5"
    assert tail(rec, "stop") == [("kind", "error"), ("reason", "an error of the program: ValueError: Unknown "
                                                    "format code 'f' for object of type 'str'")]
    assert not [text for text in said if "result in the record" in text]
    assert "Under way at the stop" not in capsys.readouterr().err


def test_a_state_of_none_is_a_silent_missed_poll_then_the_deadline_test_and_the_sleep(tmp_path, places, clock):
    site, said = FakeSite(states={"J-1": [None, None, STATE("COMPLETED", True, True)]}), []
    assert live(write_manifest(tmp_path / "m"), site, places, clock, said) == 0
    rec = records_of(places)[0]
    assert events_of(rec)[-7:] == ["submitting", "submitted", "status", "result", "rule", "rule", "end"]
    assert tail(rec, "status") == [("order", 1), ("name", "J1"), ("id", "J-1"), ("state", "COMPLETED"), ("poll", 1)]
    assert dict(tail(rec, "result"))["polls"] == 1
    assert [c for c in site.calls if c[0] == "status"] == [("status", "J-1")] * 3
    assert clock.t == 2 * site.poll_seconds


def test_a_state_of_none_to_the_deadline_stops_at_the_timeout_with_no_state(tmp_path, places, clock):
    site, said = FakeSite(states={"J-1": [None]}), []
    assert live(write_manifest(tmp_path / "m"), site, places, clock, said) == 2
    rec = records_of(places)[0]
    assert events_of(rec)[-3:] == ["submitting", "submitted", "stop"]
    reason = "order 1 (J1), job J-1: still None after 60 s. Not cancelled: the job stays open and a resume collects it"
    assert tail(rec, "stop") == [("reason", reason), ("kind", "timeout"), ("order", 1), ("name", "J1"), ("id", "J-1"),
                                 ("state", None)]
    assert said[-2] == f"STOP: {reason}"
    assert [c for c in site.calls if c[0] == "status"] == [("status", "J-1")] * 13


def test_a_job_noted_before_an_init_job_keeps_that_order_on_the_stop_line(tmp_path, places, clock):
    def prepare(job, note):
        note("created", job=7)
        note("init_created", init_job=5)
        raise KeyboardInterrupt()

    site, said = FakeSite("vlq", seconds_left=3600), []
    site.prepare = prepare
    assert live(write_manifest(tmp_path / "m", site="vlq"), site, places, clock, said) == 130
    rec = records_of(places)[0]
    assert tail(rec, "stop") == [("kind", "interrupt"), ("reason", INTERRUPTED), ("order", 1), ("name", "J1"),
                                 ("phase", "prepare"), ("id", 7), ("init_job", 5)]
    assert said[-1] == "Under way at the stop: order 1 (J1), job 7 and init job 5."


def test_a_job_id_of_none_from_the_job_request_is_on_the_stop_line_of_an_interrupt_in_the_wait(
        tmp_path, places, clock):
    site, said = FakeSite(submits={1: ("id", None)}, states={None: [interrupt]}), []
    assert live(write_manifest(tmp_path / "m"), site, places, clock, said) == 130
    rec = records_of(places)[0]
    assert dict(tail(rec, "submitted"))["id"] is None
    assert tail(rec, "stop") == [("kind", "interrupt"), ("reason", INTERRUPTED), ("order", 1), ("name", "J1"),
                                 ("id", None)]
    assert not [text for text in said if text.startswith("Under way")]
