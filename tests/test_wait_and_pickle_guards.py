"""An interrupt or a SIGTERM in the sleep between two polls, or two reads of a result, ends the call; a hostile VLQ
results file runs nothing.
"""

import functools
import os
import pickle
import signal
import subprocess
import time

import pytest
from fakes import STATE, FakeSite, cfg, lines_of, records_of, vlq, write_manifest

from qdevices import runner
from qdevices.sites import pickle_reader
from qdevices.sites.base import NoAnswer


def _sleep_that_stops(how: str, clock):
    """A sleep whose first call raises KeyboardInterrupt or sends this process a SIGTERM; then the clock's sleep."""
    calls = []

    def sleep(seconds: float) -> None:
        calls.append(seconds)
        if len(calls) > 1:
            return clock.sleep(seconds)
        if how == "ctrl-c":
            raise KeyboardInterrupt()
        os.kill(os.getpid(), signal.SIGTERM)
        return clock.sleep(seconds)

    return sleep


@pytest.mark.parametrize("how", ["ctrl-c", "sigterm"])
def test_an_interrupt_in_the_sleep_between_two_polls_ends_the_call(tmp_path, places, clock, how):
    site = FakeSite(states={"J-1": [STATE(), STATE("COMPLETED", final=True, ok=True)]})
    code = runner.send(write_manifest(tmp_path / "m"), site, cfg=cfg(), places=places, clock=clock,
                       sleep=_sleep_that_stops(how, clock), host="h", say=lambda *a, **k: None, max_order=2)
    stop = lines_of(records_of(places)[0])[-1]
    assert code == 130
    assert (stop["event"], stop["kind"], stop["id"]) == ("stop", "interrupt", "J-1")
    assert [c for c in site.calls if c[0] == "submit"] == [("submit", 1)]


class _ResultMissedOnce(FakeSite):
    """A site whose first read of a result gets no answer, a missed poll; the next read gives the result."""

    def result(self, job_id):
        if not [c for c in self.calls if c[0] == "result"]:
            self.calls.append(("result", job_id))
            raise NoAnswer("no answer", step="result")
        return super().result(job_id)


@pytest.mark.parametrize("how", ["ctrl-c", "sigterm"])
def test_an_interrupt_in_the_sleep_between_two_reads_of_a_result_ends_the_call(tmp_path, places, clock, how):
    site = _ResultMissedOnce()
    stopping = _sleep_that_stops(how, clock)

    def sleep(seconds: float) -> None:
        if site.calls[-1][0] == "result":       # only the sleep after the missed read of the result
            return stopping(seconds)
        return clock.sleep(seconds)

    code = runner.send(write_manifest(tmp_path / "m"), site, cfg=cfg(), places=places, clock=clock, sleep=sleep,
                       host="h", say=lambda *a, **k: None, max_order=2)
    lines = lines_of(records_of(places)[0])
    assert code == 130
    assert (lines[-1]["event"], lines[-1]["kind"], lines[-1]["id"]) == ("stop", "interrupt", "J-1")
    assert [c for c in site.calls if c[0] in ("submit", "result")] == [("submit", 1), ("result", "J-1")]
    assert (lines[-2]["event"], lines[-2]["step"], lines[-2]["missed"]) == ("status", "result", "no answer")
    assert "result" not in [e["event"] for e in lines]


class _Calls:
    """A pickle that calls a name with these arguments when it is loaded by a reader that trusts it."""

    def __init__(self, fn, *args) -> None:
        self.fn, self.args = fn, args

    def __reduce__(self):
        return (self.fn, self.args)


def _hostile(name: str, marker) -> bytes:
    """A pickle that names `module.name` and, run for real, makes the marker file (partial: makes a real callable)."""
    code = f"open({str(marker)!r}, 'w').close()"
    made = {"builtins.eval": (eval, code), "builtins.exec": (exec, code), "os.system": (os.system, f"touch {marker}"),
            "subprocess.Popen": (subprocess.Popen, ["touch", str(marker)]),
            "functools.partial": (functools.partial, exec, code)}[name]
    data = pickle.dumps(_Calls(*made), protocol=0, fix_imports=False).replace(b"cposix\nsystem\n", b"cos\nsystem\n")
    module, _, attribute = name.partition(".")
    assert f"c{module}\n{attribute}\n".encode() in data
    return data


HOSTILE = ["builtins.eval", "builtins.exec", "os.system", "subprocess.Popen", "functools.partial"]


@pytest.mark.parametrize("name", HOSTILE)
def test_a_vlq_results_file_that_names_a_hostile_callable_runs_nothing_and_stops_the_order(tmp_path, name):
    marker = tmp_path / "ran"
    places, clock, fake, m, site = vlq.make_vlq(tmp_path)
    fake.results_pkl = _hostile(name, marker)
    assert vlq.go(m, site, places, clock, max_order=1) == 1
    last = lines_of(records_of(places)[0])[-1]
    assert (last["event"], last["kind"], last["step"]) == ("stop", "result_error", "result")
    assert repr(pickle_reader.loads(fake.results_pkl)).startswith("<stub ")
    time.sleep(0.2 if name == "subprocess.Popen" else 0)     # a process that a real Popen started has ended
    assert not marker.exists()
