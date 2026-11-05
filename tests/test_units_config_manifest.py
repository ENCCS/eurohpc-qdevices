"""Unit tables of the config and the manifest: defaults, refusals, faults, unreadable manifests and key order."""

import json

import pytest
from fakes import write_manifest

from qdevices import config, manifest
from qdevices.sites import SITES

REFUSED = {             # texts that config.parse refuses; each refusal is in the golden
    "not_toml": "[vlq\n",
    "unknown_table": "[secrets]\na = 1\n[zeta]\nb = 2\n",
    "not_a_table": "vlq = 5\n",
    "unknown_key": '[vlq]\ntoken = "x"\n',
    "key_of_another_site": '[euroqexa]\nlexis_projects = ["x"]\n',
    "window_at_vlq": '[vlq]\nwindow = ["Mon 09:00-12:00"]\n',
    "wrong_type": '[vlq]\nbudget_seconds = "600"\n',
    "a_bool": "[vlq]\nmax_shots = true\n",
    "site_max_shots_not_whole": "[piastq]\nsite_max_shots = 400.0\n",
    "zone_not_a_text": "[piastq]\nwindow_zone = 1\n",
    "not_finite": "[vlq]\nwait_seconds = inf\n",
    "not_texts": "[vlq]\nprojects = [1]\n",
    "window_not_texts": "[piastq]\nwindow = [1]\n",
    "window_form": '[piastq]\nwindow = ["weekdays"]\n',
    "window_wraps": '[piastq]\nwindow = ["Fri-Mon 09:00-17:00"]\n',
    "window_empty": '[piastq]\nwindow = ["Mon 09:00-09:00"]\n',
    "window_zone": '[piastq]\nwindow = ["Mon 09:00-12:00"]\nwindow_zone = "Europe/Nowhere"\n',
}
HEAD = {"format": "qdevices/1", "site": "euroqexa", "machine": "M1", "project": "TEST-PROJECT"}
UNREAD = {              # texts that manifest.read gives no manifest for
    "not_json": "{",
    "a_list": "[]",
    "site_unknown": json.dumps({"format": "x", "site": "nowhere"}),
    "no_jobs": json.dumps({**HEAD, "jobs": []}),
    "a_job_not_an_object": json.dumps({**HEAD, "jobs": [{"order": 1}, 2]}),
}
FAULTS = {"format": "qdevices/2", "site": "vlq", "machine": "VLQ", "project": "", "lexis_project": 5, "run": "x/y",
          "jobs": [
              {"order": 2, "name": 7, "file": "..", "sha256": "a" * 63, "shots": True, "options": {"no_modify": True}},
              {"order": 1, "name": "J2", "file": "J2.qasm", "sha256": "b" * 64, "shots": 1.5, "options": []},
              {"order": 3, "file": "J3.qasm"}]}


def test_an_empty_config_gives_each_site_the_full_table_of_defaults(golden):
    parsed = config.parse("")
    assert tuple(parsed) == ("euroqexa", "vlq", "piastq") and {len(table) for table in parsed.values()} == {11}
    golden("units_config_defaults", "".join(f"[{site}] {key} = {value!r}\n" for site, table in parsed.items()
                                            for key, value in table.items()))


def test_the_sites_of_the_config_are_the_sites_of_the_app():
    assert tuple(SITES) == ("euroqexa", "vlq", "piastq") == tuple(config.parse(""))


def test_every_refusal_of_the_config_in_full(golden, tmp_path):
    lines = []
    for name, text in REFUSED.items():
        with pytest.raises(config.ConfigError) as caught:
            config.parse(text)
        lines.append(f"{name}: {caught.value}\n")
    (tmp_path / "folder.toml").mkdir()
    with pytest.raises(config.ConfigError) as caught:
        config.load(tmp_path / "folder.toml")
    golden("units_config_refusals", "".join(lines) + f"a_folder: {caught.value}\n")


def test_a_config_that_is_not_utf8_is_a_config_error(tmp_path):
    """The command line says REFUSED, not a traceback."""
    path = tmp_path / "qdevices.toml"
    path.write_bytes(b'[vlq]\nprojects = ["\xff"]\n')
    with pytest.raises(config.ConfigError) as refused:
        config.load(path)
    assert str(refused.value) == f"{path} cannot be read: it is not UTF-8 text"


def test_a_manifest_with_many_faults_gives_each_problem_in_order(golden, tmp_path):
    (tmp_path / "f").mkdir()
    path = tmp_path / "f" / "manifest.json"
    path.write_text(json.dumps(FAULTS))
    man, problems = manifest.read(path, SITES)
    assert man is not None and all("text" not in job for job in man["jobs"])     # no file is read after a problem
    golden("units_manifest_problems", "".join(f"{p}\n" for p in problems))


def test_a_manifest_that_cannot_be_read_gives_no_manifest_and_its_problems(golden, tmp_path):
    lines = []
    for name, text in UNREAD.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / "manifest.json").write_text(text)
        lines.append(f"{name}: {manifest.read(tmp_path / name / 'manifest.json', SITES)!r}\n")
    lines.append(f"absent: {manifest.read(tmp_path / 'absent.json', SITES)!r}\n")
    golden("units_manifest_unread", "".join(lines))


def test_a_file_changed_after_the_manifest_was_read_is_refused_before_it_is_sent(golden, tmp_path):
    man = manifest.load(write_manifest(tmp_path / "m"), SITES)
    (tmp_path / "m" / "J2.qasm").write_bytes(b"OPENQASM 2.0;\n")
    assert manifest.file_bytes(man, man["jobs"][0]) == man["jobs"][0]["text"]
    with pytest.raises(manifest.ManifestError) as caught:
        manifest.file_bytes(man, man["jobs"][1])
    golden("units_manifest_changed_file", f"{caught.value}\n")


def test_the_keys_and_values_of_a_manifest_and_of_its_jobs_in_their_order(golden, tmp_path):
    path = write_manifest(tmp_path / "m", jobs=(("J1", 10), ("J2", 20)), note="a fact of the experiment")
    data = json.loads(path.read_text())
    data["jobs"][1] = {"options": {"no_modify": True}, "label": "x", **data["jobs"][1]}     # options first
    path.write_text(json.dumps(data))
    man = manifest.load(path, SITES)
    lines = [f"{key}: {value!r}\n" for key, value in man.items() if key != "jobs"]
    lines += [f"job {job['order']} {key}: {value!r}\n" for job in man["jobs"] for key, value in job.items()]
    golden("units_manifest_keys", "".join(lines))
