"""Section 7: a Piast-Q window that wraps or is empty, or an unknown zone, is refused when the config is read."""

import json

import pytest
from fakes import CONFIG, FakeClock, places_in

from qdevices import cli, config
from qdevices.config import Windows


def piastq(windows: list[str], zone: str = "Europe/Warsaw") -> str:
    """The text of a [piastq] table with these windows and this zone."""
    return f"[piastq]\nwindow = {json.dumps(windows)}\nwindow_zone = {json.dumps(zone)}\n"


@pytest.mark.parametrize("window", ["Fri-Mon 09:00-17:00", "Mon 22:00-02:00", "Mon 09:00-09:00"])
def test_a_window_that_wraps_or_is_empty_is_refused(window):
    with pytest.raises(config.ConfigError) as caught:
        config.parse(piastq([window]))
    assert "does not wrap" in str(caught.value) and "the form 'Wed-Thu 14:00-18:00'" in str(caught.value)


def test_a_wrap_given_as_two_windows_is_taken(clock):
    windows = Windows(config.parse(piastq(["Fri-Sun 22:00-24:00", "Mon 00:00-02:00"]))["piastq"]["window"], "UTC")
    monday = clock.start                                                       # Monday 2026-01-05 12:00 UTC
    assert windows.holds(monday.replace(day=11, hour=23))                      # Sunday
    assert windows.holds(monday.replace(hour=1, minute=59))
    assert not windows.holds(monday.replace(hour=2))
    assert not windows.holds(monday.replace(day=8, hour=23))                   # Thursday


@pytest.mark.parametrize("zone", ["Europe/Nowhere", "", "../UTC"])
def test_a_window_zone_that_is_not_known_is_refused_when_a_window_is_set(zone):
    with pytest.raises(config.ConfigError, match="is not a known time zone"):
        config.parse(piastq(["Mon 09:00-12:00"], zone))
    assert config.parse(f"[piastq]\nwindow_zone = {json.dumps(zone)}\n")["piastq"]["window"] == []


def test_check_and_runs_refuse_a_zone_that_is_not_known_with_no_traceback(tmp_path, capsys):
    places = places_in(tmp_path)
    places.config.write_text(CONFIG.replace("[piastq]\n", piastq(["Mon 09:00-12:00"], "Europe/Nowhere")))
    clock = FakeClock()
    for args in (["check", "piastq"], ["runs"]):
        assert cli.main(args, places=places, environ={}, clock=clock, sleep=clock.sleep, host="host-a") == 1
        out = capsys.readouterr().out
        assert "REFUSED: [piastq] window_zone 'Europe/Nowhere' is not a known time zone" in out
        assert "outside now" not in out and "inside now" not in out
