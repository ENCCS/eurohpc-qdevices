"""The saved reads: a list of machines is not the read of one, and the dry run says how old its read is."""

import json

from fakes import TOKEN, FakeSite, cfg, write_manifest

from qdevices import check, dryrun

TWO_QUBITS = b'OPENQASM 2.0;\ninclude "qelib1.inc";\nqreg q[2];\ncreg c[2];\nx q[0];\nmeasure q -> c;\n'
LIST = {"resources": {"M1": {"qubits": 1, "online": True}, "M2": {"qubits": 9, "online": False}}}


def save(places, name: str, read: dict) -> None:
    folder = places.reads / "euroqexa"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(json.dumps(read))


def dry(path, places, clock, **kw) -> tuple[int, str]:
    out = []
    code = dryrun.dry_run(path, cfg=cfg(), places=places, clock=clock, say=out.append, **kw)
    return code, "\n".join(out)


def test_check_live_without_a_manifest_stores_a_list_not_a_read(places, clock):
    out = []
    assert check.check("euroqexa", live=True, token=TOKEN, manifest_path=None, cfg=cfg(), places=places, clock=clock,
                       sleep=clock.sleep, host="host-a", make_site=lambda *a, **k: FakeSite(read=LIST),
                       say=out.append) == 0
    names = [p.name for p in (places.reads / "euroqexa").iterdir()]
    assert names == ["list_20260105T120000Z.json"] and "  M1: 1 qubits, online True" in out


def test_the_dry_run_takes_the_read_of_the_machine_not_a_newer_list(tmp_path, places, clock):
    save(places, "read_20260105T100000Z.json", {"read_at": "2026-01-05T10:00:00+00:00", "machine": "M1",
                                               "qubits": 1, "gate_names": ["cz", "r"]})
    save(places, "read_20260105T110000Z.json", {"read_at": "2026-01-05T11:00:00+00:00", **LIST})   # an older list
    save(places, "read_20260105T113000Z.json", {"read_at": "2026-01-05T11:30:00+00:00", "machine": "M2", "qubits": 9})
    save(places, "list_20260105T114000Z.json", {"read_at": "2026-01-05T11:40:00+00:00", **LIST})
    path = write_manifest(tmp_path / "m", jobs=(("J1", 10),), text=TWO_QUBITS)
    data = json.loads(path.read_text())
    data["jobs"][0]["options"] = {"no_modify": True}
    path.write_text(json.dumps(data))
    code, out = dry(path, places, clock)
    assert code == 1
    assert "read_20260105T100000Z.json, 2.0 hours old" in out and "older than 24 hours" not in out
    assert "the text declares 2 qubits, the machine has 1" in out and "are not among the gates" in out


def test_a_read_older_than_24_hours_gets_a_note(tmp_path, places, clock):
    path = write_manifest(tmp_path / "m")
    save(places, "read_20260104T060000Z.json", {"read_at": "2026-01-04T06:00:00+00:00", "machine": "M1", "qubits": 5})
    code, out = dry(path, places, clock)
    assert code == 0 and "30.0 hours old" in out
    assert "the read is older than 24 hours" in out and "qdevices check euroqexa --live --manifest" in out
    save(places, "read_20260105T110000Z.json", {"read_at": "2026-01-05T11:00:00+00:00", "machine": "M1", "qubits": 5})
    code, out = dry(path, places, clock)
    assert code == 0 and "1.0 hours old" in out and "older than 24 hours" not in out


def test_a_folder_with_only_a_list_says_no_read_of_the_machine_is_saved(tmp_path, places, clock):
    save(places, "read_20260105T110000Z.json", {"read_at": "2026-01-05T11:00:00+00:00", **LIST})   # an older list
    save(places, "list_20260105T114000Z.json", {"read_at": "2026-01-05T11:40:00+00:00", **LIST})
    code, out = dry(write_manifest(tmp_path / "m"), places, clock)
    assert code == 0 and "no read of M1 is saved" in out


def test_a_read_given_with_read_fails_the_dry_run_when_it_is_a_list_or_of_another_machine(tmp_path, places, clock):
    save(places, "list_20260105T114000Z.json", {"read_at": "2026-01-05T11:40:00+00:00", **LIST})
    save(places, "read_20260105T113000Z.json", {"read_at": "2026-01-05T11:30:00+00:00", "machine": "M2", "qubits": 9})
    save(places, "read_20260105T110000Z.json", {"read_at": "2026-01-05T11:00:00+00:00", "machine": "M1", "qubits": 5})
    path, folder = write_manifest(tmp_path / "m"), places.reads / "euroqexa"
    for name, expected, says in (("list_20260105T114000Z.json", 1, "names no machine, so it is not a read of M1"),
                                 ("read_20260105T113000Z.json", 1, "is a read of M2, not of M1"),
                                 ("read_20260105T110000Z.json", 0, "read_20260105T110000Z.json, 1.0 hours old")):
        code, out = dry(path, places, clock, read_file=folder / name)
        assert code == expected and says in out
        assert ("  FAILED: " + str(folder / name) in out) == (expected == 1)
