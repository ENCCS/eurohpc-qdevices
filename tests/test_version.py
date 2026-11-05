"""One version: the project table of pyproject.toml, the version line of CITATION.cff and qdevices.__version__."""

import re
import shutil
import tomllib
from pathlib import Path

import pytest

import qdevices

ROOT = Path(__file__).resolve().parent.parent
CITED = re.compile(r"^version:[ \t]*(.*?)[ \t]*$", re.MULTILINE)      # the key at the top, not cff-version
CHANGES = {              # case: the file of a copy, a text in it, and the text put in its place
    "pyproject": ("pyproject.toml", '\nversion = "', '\nversion = "9.'),
    "citation": ("CITATION.cff", "\nversion: ", "\nversion: 9."),
    "no citation line": ("CITATION.cff", "\nversion: ", "\n# version: "),
}


def check(root: Path, package: str) -> None:
    """Fails unless pyproject.toml and CITATION.cff in `root` each state one version, and `package` is that one."""
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    cited = [found.strip("'\"") for found in CITED.findall((root / "CITATION.cff").read_text(encoding="utf-8"))]
    assert cited == [project] and package == project, f"pyproject.toml {project}, CITATION.cff {cited}, {package}"


def test_pyproject_citation_and_the_package_state_one_version():
    check(ROOT, qdevices.__version__)


@pytest.mark.parametrize("case", list(CHANGES))
def test_a_copy_with_one_version_changed_fails_the_check(tmp_path, case):
    name, old, new = CHANGES[case]
    for file in ("pyproject.toml", "CITATION.cff"):
        shutil.copy(ROOT / file, tmp_path / file)
    text = (tmp_path / name).read_text(encoding="utf-8")
    assert old in text
    (tmp_path / name).write_text(text.replace(old, new, 1), encoding="utf-8")
    with pytest.raises(AssertionError):
        check(tmp_path, qdevices.__version__)


def test_a_package_of_another_version_fails_the_check():
    with pytest.raises(AssertionError):
        check(ROOT, "0.0.0")
