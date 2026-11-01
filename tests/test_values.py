"""The small helpers of values.py on a table of values: the integer test, the number test and the digest."""

import math

import pytest

from qdevices.values import is_int, is_number, sha256_hex

VALUES = [              # (value, is_int, is_number)
    (True, False, False),
    (False, False, False),
    (0, True, True),
    (-7, True, True),
    (2**64, True, True),
    (0.0, False, True),
    (1.5, False, True),
    (math.nan, False, True),
    (math.inf, False, True),
    (-math.inf, False, True),
    ("1", False, False),
    (None, False, False),
    (b"1", False, False),
]


@pytest.mark.parametrize("value, integer, number", VALUES)
def test_the_integer_and_number_tests_of_a_value(value, integer, number):
    assert is_int(value) is integer
    assert is_number(value) is number


def test_the_digest_of_some_bytes_is_its_sha256_in_hexadecimal():
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
