"""Faults 9, 16 and 32 of the plan: the small ones, each with a plain fix."""

import os
import subprocess
import sys

from qdevices import __version__, redact
from qdevices.runner.resume import cut_entry


def test_the_forms_of_a_secret_are_in_a_fixed_order_the_secret_then_its_json_form():
    secret = 'abcdefgh"ijklmnop'
    assert redact._forms(secret) == [secret, 'abcdefgh\\"ijklmnop']
    assert redact._forms("abcdefghijk") == ["abcdefghijk"]


def test_a_text_id_cut_just_after_an_escaped_quote_may_be_cut():
    entry = cut_entry(4, '{"event": "submitted", "order": 1, "id": "ab\\"')
    assert (entry["job_id"], entry["job_id_may_be_cut"]) == ('ab\\"', True)
    whole = cut_entry(4, '{"event": "submitted", "order": 1, "id": "ab\\"c", "submitted_')
    assert (whole["job_id"], whole["job_id_may_be_cut"]) == ('ab\\"c', False)


def test_the_version_and_the_help_work_under_python_oo():
    found = subprocess.run([sys.executable, "-OO", "-m", "qdevices", "--version"], capture_output=True, text=True,
                           check=False)
    assert (found.returncode, found.stdout.strip()) == (0, f"qdevices {__version__}")
    helped = subprocess.run([sys.executable, "-OO", "-m", "qdevices", "--help"], capture_output=True, text=True,
                            check=False)
    assert helped.returncode == 0 and helped.stdout.startswith("usage: qdevices")


def test_a_euroqexa_value_given_as_a_set_literal_is_read_in_sorted_order_whatever_the_hash_seed():
    code = ("from qdevices.sites import euroqexa; "
            "print(euroqexa._plain(euroqexa._literal(\"{'prx', 'cz', 'measure', 'r', 'barrier', 'move'}\")))")
    seen = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                           env={**os.environ, "PYTHONHASHSEED": str(seed)}).stdout for seed in range(8)}
    assert seen == {"['barrier', 'cz', 'measure', 'move', 'prx', 'r']\n"}
