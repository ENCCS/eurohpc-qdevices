"""Golden transcripts of the runner: each call's exit code and every line it printed on stdout and stderr."""

import pytest
from fakes import FakeSite, records_of, write_manifest
from fakes.piastq import EXPIRED, Broker, answer, piastq_manifest
from runner_calls import Calls, ctrl_c
from test_golden_records import RECORDS
from test_golden_stops import STOPS

from qdevices.sites import piastq

TRACEBACK = "Traceback (most recent call last):"


def without_frames(text: str) -> str:
    """The text without traceback frames, which every refactor moves: the indented lines after the first line."""
    kept, frames = [], False
    for line in text.splitlines(keepends=True):
        if frames and line.startswith(" "):
            continue
        frames = line.startswith(TRACEBACK)
        kept.append(line)
    return "".join(kept)


def transcript(calls: Calls) -> str:
    """Each call in turn: its exit code, what it printed on stdout, then what it printed on stderr."""
    return "".join(f"=== call {n}: exit {code}\n--- stdout\n{out}--- stderr\n{without_frames(err)}"
                   for n, (code, (out, err)) in enumerate(zip(calls.codes, calls.printed, strict=True), 1))


def piastq_wait_interrupt(calls, tmp_path, monkeypatch) -> None:
    """Ctrl-C in the wait for a job at a site whose class gives the collect note of Piast-Q."""
    site = FakeSite("piastq", states={"J-1": [ctrl_c]})
    site.collect_note = piastq.PiastQ.collect_note
    calls.send(write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 10),)), site, max_order=1)


def piastq_lost(calls, tmp_path, monkeypatch) -> None:
    """Ctrl-C in the task request leaves order 1 lost; a collect over the fake broker stops at it."""
    m = write_manifest(tmp_path / "m", site="piastq", jobs=(("J1", 10),))
    calls.send(m, FakeSite("piastq", submits={1: ("interrupt",)}), max_order=1)
    calls.send(m, Broker().site(), resume=records_of(calls.places)[0])


def piastq_timeout(calls, tmp_path, monkeypatch) -> None:
    """The task is still Running at wait_seconds: it is not cancelled, and the order stays open."""
    broker = Broker(states=[answer(200, json={"status": "Running"})])
    calls.send(piastq_manifest(tmp_path / "m"), broker.site(), max_order=1)


def piastq_expired(calls, tmp_path, monkeypatch) -> None:
    """The broker answers the read of the result of a finished task that it does not know the task (code 4)."""
    broker = Broker(results=[answer(200, json=EXPIRED)])
    calls.send(piastq_manifest(tmp_path / "m"), broker.site(), max_order=1)


PIASTQ = {case.__name__: case for case in (piastq_wait_interrupt, piastq_lost, piastq_timeout, piastq_expired)}
CALLS = {**RECORDS, **STOPS, **PIASTQ}


def test_every_case_has_a_name_of_its_own():
    assert len(CALLS) == len(RECORDS) + len(STOPS) + len(PIASTQ)


def test_the_frames_of_a_traceback_are_left_out_and_the_lines_after_them_stay():
    frames = '  File "x.py", line 1, in f\n    f()\n    ^^^\n'
    text = f"before\n{TRACEBACK}\n{frames}RuntimeError: no\n  more\nFAILED: an error\n"
    assert without_frames(text) == f"before\n{TRACEBACK}\nRuntimeError: no\n  more\nFAILED: an error\n"


@pytest.mark.parametrize("case", list(CALLS))
def test_each_call_keeps_its_exit_code_and_every_line_it_printed(case, tmp_path, places, clock, monkeypatch, capsys,
                                                                   golden):
    capsys.readouterr()
    calls = Calls(places, clock, capsys)
    CALLS[case](calls, tmp_path, monkeypatch)
    golden(f"transcripts_{case}", transcript(calls))


@pytest.mark.parametrize("case", ["write_failed_result", "write_failed_failed"])
def test_a_final_line_that_cannot_be_written_names_the_job_on_stderr(case, tmp_path, places, clock, monkeypatch,
                                                                      capsys):
    capsys.readouterr()
    calls = Calls(places, clock, capsys)
    CALLS[case](calls, tmp_path, monkeypatch)
    assert calls.codes == [3]
    assert "Under way at the stop: order 1 (J1), job J-1." in calls.printed[-1].err
