"""The manifest and the config."""

import json

import pytest
from fakes import write_manifest

from qdevices import config, manifest
from qdevices.config import Windows
from qdevices.sites import SITES


def problems_of(path):
    return manifest.read(path, SITES)[1]


def edit(path, change):
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


def test_a_good_manifest_has_no_problems(tmp_path):
    m = manifest.load(write_manifest(tmp_path / "m"), SITES)
    assert m["run"] == "m" and [j["order"] for j in m["jobs"]] == [1, 2, 3]


def test_a_gap_in_the_orders_is_refused(tmp_path):
    path = write_manifest(tmp_path / "m")
    edit(path, lambda d: d["jobs"][2].update(order=4))
    assert any("without gaps" in p for p in problems_of(path))


def test_a_name_outside_the_pattern_is_refused(tmp_path):
    path = write_manifest(tmp_path / "m")
    edit(path, lambda d: d["jobs"][0].update(name="J 1"))
    assert any("[A-Za-z0-9_-]+" in p for p in problems_of(path))


def test_an_unknown_option_is_refused(tmp_path):
    path = write_manifest(tmp_path / "m")
    edit(path, lambda d: d["jobs"][0].update(options={"queued": True}))
    assert any("'queued'" in p for p in problems_of(path))
    edit(path, lambda d: d["jobs"][0].update(options={"no_modify": "yes"}))
    assert any("wrong type" in p for p in problems_of(path))


def test_a_file_outside_the_folder_is_refused(tmp_path):
    path = write_manifest(tmp_path / "m")
    edit(path, lambda d: d["jobs"][0].update(file="../J1.qasm"))
    assert any("next to the manifest" in p for p in problems_of(path))


def test_a_changed_file_is_refused(tmp_path):
    path = write_manifest(tmp_path / "m")
    (tmp_path / "m" / "J1.qasm").write_bytes(b"OPENQASM 2.0;\n")
    assert any("SHA-256" in p for p in problems_of(path))


def test_vlq_needs_a_lexis_project_and_a_resource(tmp_path):
    path = write_manifest(tmp_path / "m", site="vlq")
    edit(path, lambda d: d.pop("resource"))
    assert any('"resource"' in p for p in problems_of(path))


def test_an_unknown_config_key_or_table_is_refused():
    with pytest.raises(config.ConfigError, match="unknown key"):
        config.parse('[vlq]\ntoken = "x"\n')
    with pytest.raises(config.ConfigError, match="unknown table"):
        config.parse('[secrets]\na = 1\n')
    with pytest.raises(config.ConfigError, match="unknown key"):
        config.parse('[euroqexa]\nlexis_projects = ["x"]\n')


def test_the_window_of_config(clock):
    conf = config.parse('[piastq]\nwindow = ["Mon 09:00-12:00", "Wed-Thu 14:00-18:00"]\n'
                        'window_zone = "Europe/Warsaw"\n')
    windows = Windows(conf["piastq"]["window"], "UTC")
    monday = clock.start                                   # Monday 2026-01-05 12:00 UTC
    assert windows.holds(monday.replace(hour=9, minute=30))
    assert not windows.holds(monday.replace(hour=8, minute=59))
    assert windows.holds(monday.replace(day=7, hour=14))      # Wednesday
    assert not windows.holds(monday.replace(day=9, hour=15))  # Friday
    with pytest.raises(config.ConfigError, match="form"):
        config.parse('[piastq]\nwindow = ["weekdays"]\n')


def test_no_config_file_allows_no_project(tmp_path):
    conf = config.load(tmp_path / "absent.toml")
    assert conf["vlq"]["projects"] == [] and conf["vlq"]["budget_seconds"] is None


@pytest.mark.parametrize("first", [1.0, True])
def test_an_order_that_is_not_a_whole_number_is_refused_as_out_of_sequence(tmp_path, first):
    """An order of 1.0 or true is equal to 1, but the ledger folds only whole numbers: its lines would be unseen."""
    path = write_manifest(tmp_path / "m")
    edit(path, lambda d: d["jobs"][0].update(order=first))
    assert problems_of(path) == ["the orders must be 1 to N in sequence, without gaps"]
