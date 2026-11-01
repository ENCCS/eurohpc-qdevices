"""The load of a rules file: read once, and the bytes that run are the bytes that are hashed."""

import hashlib
import os

import pytest

from qdevices import rulebook


def test_the_rules_file_is_read_once_and_the_bytes_that_run_are_hashed(tmp_path):
    assert rulebook.load(None) == ({}, None)
    path = tmp_path / "rules.py"
    text = "def before_job(job, state):\n    return {'rule': 'r', 'passed': 1 == 1}\n"
    path.write_text(text)
    hooks, first = rulebook.load(path)
    assert hooks["before_job"]({}, {})["passed"] is True
    same = path.stat()
    path.write_text(text.replace("1 == 1", "1 == 2"))               # the same size and, below, the same time:
    os.utime(path, ns=(same.st_atime_ns, same.st_mtime_ns))        # a bytecode cache would run the old code
    hooks, second = rulebook.load(path)
    assert hooks["before_job"]({}, {})["passed"] is False
    assert second == {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    assert second["sha256"] != first["sha256"] and not (tmp_path / "__pycache__").exists()
    with pytest.raises(rulebook.RuleFileError, match="no rules file at"):
        rulebook.load(tmp_path / "absent.py")


def test_a_rules_file_that_rewrites_itself_during_the_import_is_hashed_and_run_from_its_first_bytes(tmp_path):
    path = tmp_path / "rules.py"
    later = "def before_job(job, state):\n    return {'rule': 'r', 'passed': False}\n"
    text = ("from pathlib import Path\n\n"
            f"Path(__file__).write_text({later!r})          # the file rewrites itself while it is imported\n\n\n"
            "def before_job(job, state):\n    return {'rule': 'r', 'passed': True}\n")
    path.write_text(text)
    hooks, held = rulebook.load(path)
    assert path.read_text() == later                                    # the file did change during the import
    assert held == {"path": str(path.resolve()), "sha256": hashlib.sha256(text.encode()).hexdigest()}
    assert hooks["before_job"]({}, {})["passed"] is True                # the hooks of the first bytes


@pytest.mark.parametrize("raised, text", [("SystemExit(7)", "SystemExit: 7"), ("GeneratorExit()", "GeneratorExit: ")],
                         ids=["SystemExit", "GeneratorExit"])
def test_a_rules_file_that_raises_an_exit_at_its_import_is_refused(tmp_path, raised, text):
    path = tmp_path / "rules.py"
    path.write_text(f"raise {raised}\n")
    with pytest.raises(rulebook.RuleFileError) as refused:
        rulebook.load(path)
    assert str(refused.value) == f"the rules file {path} cannot be loaded: {text}"


def test_a_rules_file_that_raises_an_interrupt_at_its_import_is_still_an_interrupt(tmp_path):
    path = tmp_path / "rules.py"
    path.write_text("raise KeyboardInterrupt\n")
    with pytest.raises(KeyboardInterrupt):
        rulebook.load(path)
