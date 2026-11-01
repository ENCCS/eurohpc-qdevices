"""`resolve --job` on an open order whose last stop is submit_unknown: refused, with the same text at every site."""

import json

import pytest
from fakes import FakeClock

from qdevices import runner
from qdevices.resolve import resolve

TEXT = ("has the job u-1 already. When the site shows it past Configuring, a resume collects it; when the site shows "
        "that it never ran, give --none")


def _submit_unknown(places, site: str):
    """A record of the app, written by hand, whose order 1 has the job u-1 and the last stop submit_unknown."""
    rec = places.records / site / "su" / "run_20260101T100000Z.jsonl"
    rec.parent.mkdir(parents=True)
    rows = [{"event": "start", "utc": "2026-01-01T10:00:00+00:00", "app": "qdevices", "site": site, "machine": "M1",
             "project": "TEST-PROJECT", "run": "su", "jobs": [{"order": 1, "name": "J1"}]},
            {"event": "submitting", "utc": "2026-01-01T10:00:01+00:00", "order": 1, "name": "J1"},
            {"event": "submitted", "utc": "2026-01-01T10:00:02+00:00", "order": 1, "name": "J1", "job": "u-1"},
            {"event": "stop", "utc": "2026-01-01T10:00:03+00:00", "order": 1, "kind": "submit_unknown"}]
    rec.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return rec


@pytest.mark.parametrize("site", ["euroqexa", "vlq", "piastq"])
def test_the_refusal_names_the_state_configuring_at_every_site(places, site):
    rec = _submit_unknown(places, site)
    before = rec.read_bytes()
    with pytest.raises(runner.Refused) as refused:
        resolve(rec, 1, "X", places=places, clock=FakeClock(), host="host-a")
    assert str(refused.value) == f"order 1 of {rec} {TEXT}" and rec.read_bytes() == before
