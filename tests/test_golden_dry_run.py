"""`qdevices dry-run` pinned whole: its lines and exit code, for each site and for the faults of a manifest.

The command line gives the dry run no clock: the app clock ages a saved read, so each test fakes it.
"""

import json

from fakes import CONFIG, QASM, FakeClock, write_manifest
from fakes.piastq import PAYLOAD
from fakes.vlq import VLQ_TEXT

from qdevices import cli
from qdevices import clock as clocks
from qdevices.layout import Layout
from qdevices.sites.euroqexa import EuroQExa

LIMIT = EuroQExa.max_shots_times_gates
PIN = Layout.of(5, [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)]).fields
NO_VLQ_BUDGET = CONFIG.replace('lexis_projects = ["TEST-LEXIS"]\nbudget_seconds = 1000\n',
                               'lexis_projects = ["TEST-LEXIS"]\n')
SITE_MAX_SHOTS = CONFIG.replace("[piastq]\n", "[piastq]\nsite_max_shots = 400\n")
FAULTS = {"format": "qdevices/0", "site": "euroqexa", "machine": "", "project": 7, "run": "a run", "jobs": [
    {"order": 1, "name": "J 1", "file": "../J1.qasm", "sha256": "ABC", "shots": 0, "options": {"queued": True}},
    {"order": 3, "name": "J2", "file": "J2.qasm", "sha256": "0" * 64, "shots": 10, "options": {"no_modify": "yes"}},
    {"order": 4, "name": "J3"}]}


def dry_run(capsys, monkeypatch, places, *args) -> str:
    """`qdevices dry-run ARGS`: the exit code, then stdout and stderr, in one text."""
    clock, made = FakeClock(), []
    monkeypatch.setattr(clocks.CLOCK, "utc", clock.utc)
    code = cli.main(["dry-run", *map(str, args)], places=places, environ={}, clock=clock, sleep=clock.sleep,
                    make_site=lambda *a, **k: made.append(a), host="host-a")
    out = capsys.readouterr()
    assert made == []                                                  # the dry run makes no site
    return f"exit {code}\n--- stdout\n{out.out}--- stderr\n{out.err}"


def save(places, name: str, read: dict) -> None:
    """A saved read of Euro-Q-Exa, in the folder where `check --live` stores it."""
    folder = places.reads / "euroqexa"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(read))


def faulty(folder, data: dict):
    """A manifest of this data, with no circuit file next to it."""
    folder.mkdir()
    (folder / "manifest.json").write_text(json.dumps(data))
    return folder / "manifest.json"


def test_euroqexa_with_a_pin_a_read_30_hours_old_and_a_job_above_the_limit(capsys, monkeypatch, places, golden,
                                                                           tmp_path):
    places.config.write_text(CONFIG)
    save(places, "read_20260104T060000Z.json", {"read_at": "2026-01-04T06:00:00+00:00", "machine": "M1", **PIN})
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", LIMIT // 2 + 1)), layout=PIN)    # two gates each
    golden("dry_run_euroqexa", dry_run(capsys, monkeypatch, places, m))


def test_euroqexa_with_a_pin_and_no_saved_read_passes(capsys, monkeypatch, places, golden, tmp_path):
    places.config.write_text(CONFIG)
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10),), layout=PIN)
    golden("dry_run_euroqexa_no_read", dry_run(capsys, monkeypatch, places, m))


def test_vlq_with_the_cost_of_each_job_and_no_budget_seconds(capsys, monkeypatch, places, golden, tmp_path):
    assert NO_VLQ_BUDGET != CONFIG
    places.config.write_text(NO_VLQ_BUDGET)
    m = write_manifest(tmp_path / "m", site="vlq", jobs=(("V1", 10), ("V2", 5000)), text=VLQ_TEXT)
    golden("dry_run_vlq", dry_run(capsys, monkeypatch, places, m))


def test_piastq_with_site_max_shots_400_in_the_config(capsys, monkeypatch, places, golden, tmp_path):
    places.config.write_text(SITE_MAX_SHOTS)
    m = write_manifest(tmp_path / "m", site="piastq", jobs=(("P1", 100), ("P2", 500)), text=PAYLOAD)
    golden("dry_run_piastq", dry_run(capsys, monkeypatch, places, m))


def test_a_manifest_with_many_faults_fails_with_each_of_them_in_order(capsys, monkeypatch, places, golden,
                                                                      tmp_path):
    places.config.write_text(CONFIG)
    golden("dry_run_faults", dry_run(capsys, monkeypatch, places, faulty(tmp_path / "f", FAULTS)))


def test_a_manifest_whose_head_cannot_be_read_fails_at_once(capsys, monkeypatch, places, golden, tmp_path):
    places.config.write_text(CONFIG)
    head = faulty(tmp_path / "f", {"format": "qdevices/0", "site": "nowhere", "jobs": []})
    golden("dry_run_faults_head", dry_run(capsys, monkeypatch, places, head))


def test_a_read_given_with_read_that_is_a_list_of_machines_fails(capsys, monkeypatch, places, golden, tmp_path):
    places.config.write_text(CONFIG)
    listed = {"read_at": "2026-01-05T11:40:00+00:00", "resources": {"M1": {"qubits": 5, "online": True}}}
    save(places, "list_20260105T114000Z.json", listed)
    m = write_manifest(tmp_path / "m")
    golden("dry_run_read_list", dry_run(capsys, monkeypatch, places, m, "--read",
                                        places.reads / "euroqexa" / "list_20260105T114000Z.json"))


def test_a_manifest_whose_first_file_has_changed_checks_no_later_job(capsys, monkeypatch, places, golden, tmp_path):
    places.config.write_text(CONFIG)
    m = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 10)))
    (tmp_path / "m" / "J1.qasm").write_bytes(QASM.replace(b"x q[0];\n", b"h q[0];\nx q[0];\n"))   # three gates
    golden("dry_run_changed_file", dry_run(capsys, monkeypatch, places, m))
