"""An error of the program or an interrupt in a live call: the job id under way is shown, and no token is."""

from fakes import TOKEN, FakeSite, cfg, events, lines_of, records_of, send, write_manifest

from qdevices import record, runner
from qdevices.ledger import Ledger

JOB = 4711
STEPS = [("created", {"job": JOB}), ("uploaded", {"job": JOB})]


def fail_created_line(monkeypatch, error) -> None:
    """Record.write raises `error` once, at the "created" step line, before anything of it is written."""
    write, hit = record.Record.write, []

    def once(self, event, **fields):
        if event == "step" and fields.get("step") == "created" and not hit:
            hit.append(event)
            raise error
        return write(self, event, **fields)

    monkeypatch.setattr(record.Record, "write", once)


def vlq_send(tmp_path, places, clock, said: list) -> int:
    site = FakeSite("vlq", seconds_left=3600, submits={1: ("steps", ("id", JOB), STEPS)})
    return runner.send(write_manifest(tmp_path / "m", site="vlq"), site, cfg=cfg(), places=places, clock=clock,
                       sleep=clock.sleep, host="host-a", say=said.append, max_order=1)


def test_a_created_line_that_cannot_be_written_shows_the_job_id(tmp_path, places, clock, monkeypatch, capsys):
    fail_created_line(monkeypatch, OSError(28, "No space left on device"))
    assert vlq_send(tmp_path, places, clock, []) == 3
    err = capsys.readouterr().err
    assert (f"RECORD WRITE FAILED (OSError): order 1 (J1), job {JOB}: its created line may not be in the record; "
            "write this id down") in err
    assert f"Under way at the stop: order 1 (J1), job {JOB}." in err
    rec = records_of(places)[0]
    assert events(rec, "stop")[-1]["kind"] == "error" and events(rec, "stop")[-1]["id"] == JOB
    assert Ledger(lines_of(rec)).orders[1].status == "lost"          # no step line holds the id


def test_an_interrupt_inside_the_write_of_the_created_line_shows_the_job_id(tmp_path, places, clock, monkeypatch):
    fail_created_line(monkeypatch, KeyboardInterrupt())
    said = []
    assert vlq_send(tmp_path, places, clock, said) == 130
    assert f"Under way at the stop: order 1 (J1), job {JOB}." in said
    rec = records_of(places)[0]
    assert events(rec, "stop")[-1]["kind"] == "interrupt" and events(rec, "stop")[-1]["id"] == JOB
    assert not [e for e in lines_of(rec) if e.get("step") == "created"]


def test_the_traceback_of_an_error_of_the_program_goes_through_the_token_filter(tmp_path, places, clock, capsys):
    site = FakeSite()

    def submit(job, note, prepared=None):
        raise RuntimeError(f"a fault with {TOKEN} in it")

    site.submit = submit
    assert send(write_manifest(tmp_path / "m"), site, places, clock, max_order=1) == 3
    out, err = capsys.readouterr()
    assert "RuntimeError" in err and "FAILED: an error of the program" in err
    for text in (out, err, records_of(places)[0].read_text()):
        assert TOKEN not in text and TOKEN[:8] not in text
