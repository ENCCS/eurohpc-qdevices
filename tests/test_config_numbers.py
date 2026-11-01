"""The numbers of qdevices.toml must be finite: inf and nan, which TOML allows, are refused."""

import pytest

from qdevices import config


@pytest.mark.parametrize("key", ["award_hours", "budget_seconds", "job_seconds_limit", "wait_seconds"])
@pytest.mark.parametrize("value", ["inf", "-inf", "nan"])
def test_a_number_that_is_not_finite_is_refused(key, value):
    with pytest.raises(config.ConfigError, match=f"{key} must be a finite number"):
        config.parse(f"[vlq]\n{key} = {value}\n")


def test_a_finite_number_is_kept():
    assert config.parse("[vlq]\nwait_seconds = 1800.5\n")["vlq"]["wait_seconds"] == 1800.5
