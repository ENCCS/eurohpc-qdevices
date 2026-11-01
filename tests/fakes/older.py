"""Records of another runner, written by hand, and the helpers of the tests of the decisions on their orders."""

import json
from pathlib import Path

from fakes import CONFIG, FakeSite, cfg, send, write_manifest
from qdevices import cli, older
from qdevices.resolve import resolve

START = {"event": "start", "machine": "Piast-Q", "proposal": "TEST-AWARD", "utc": "2026-01-01T10:00:00+00:00"}
OPEN = [{"event": "submitting", "order": 1, "name": "K1"},
        {"event": "submitted", "order": 1, "name": "K1", "uid": "p-1"},
        {"event": "stop", "order": 1, "kind": "http_error", "http_status": 502},
        {"event": "stop", "order": 1, "kind": "http_error", "http_status": 502}]
LOST = [{"event": "submitting", "order": 2, "name": "K2"}]
RESULT = [{"event": "submitting", "order": 3, "name": "K3"},
          {"event": "submitted", "order": 3, "name": "K3", "uid": "p-3"},
          {"event": "result", "order": 3, "name": "K3", "uid": "p-3", "shots": 200, "wall_seconds": 500.0}]
OLDER = [START, *OPEN, *LOST]                     # a record of Piast-Q: order 1 open, order 2 lost


def write(path: Path, lines) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return path


def listed(places, **sites) -> dict:
    """CONFIG with older_records for each site named, as listed(places, piastq=[folder]); also the config file."""
    text = CONFIG
    for site, folders in sites.items():
        text = text.replace(f"[{site}]\n", f"[{site}]\nolder_records = {json.dumps([str(f) for f in folders])}\n")
    places.config.write_text(text)
    return cfg(text)


def decide(rec, order, places, clock, conf, decision=None, job=None, **kw) -> str:
    """`resolve` of one order: `decision` is "gone", "over_limit" or "expired"; else `job` is an id or None."""
    return resolve(rec, order, job, places=places, clock=clock, host="host-a", decision=decision, cfg=conf, **kw)


def decisions_file(places, site: str = "piastq") -> Path:
    return Path(places.records) / site / older.DECISIONS


def piastq_send(tmp_path, places, clock, conf, run: str = "m") -> int:
    """A send of one Piast-Q job, in a run of its own."""
    m = write_manifest(tmp_path / run, site="piastq", jobs=(("J1", 10),))
    return send(m, FakeSite("piastq"), places, clock, conf, max_order=1)


def main(places, clock, *args) -> int:
    return cli.main(list(args), places=places, environ={}, clock=clock, sleep=clock.sleep, host="host-a")


def line_of(lines: list[str], rec: Path) -> str:
    """The `runs` line of one record."""
    return next(line for line in lines if f"  {rec}: " in line)
