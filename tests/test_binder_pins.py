"""Binder's packages and Python against examples/qrisp/pixi.lock, as the lock has them for linux-64.

Binder builds on linux-64 and installs .binder/requirements.txt with pip, so each line there pins a package to the
version that the lock holds for linux-64, and .binder/runtime.txt names the Python of the lock. When the lock moves,
both follow it. Each package that the examples import has a pin there, and any other line that is not blank or a
comment is a difference. The lock is read as the text pixi writes, with no YAML parser.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS, RUNTIME = ROOT / ".binder" / "requirements.txt", ROOT / ".binder" / "runtime.txt"
LOCK = ROOT / "examples" / "qrisp" / "pixi.lock"
ITEM = re.compile(r"      - (conda|pypi): (\S+)")              # a package of one platform of an environment
ENTRY = re.compile(r"^- pypi: (\S+)\n  name: (\S+)\n  version: (\S+)$", re.MULTILINE)
NEED = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)")      # a name, then ==2.4.6, <2.5 or nothing
BINDER = {"numpy", "scipy", "matplotlib", "qutip", "qutip-qip", "qrisp"}      # what the examples import


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normal(name: str) -> str:
    """A package name as pip compares names: qutip_qip and qutip-qip are one name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def items(lock: str, platform: str) -> list[tuple[str, str]]:
    """Each kind (conda or pypi) and URL that the lock lists for the default environment on one platform."""
    lines = iter(lock.splitlines())
    for head in ("environments:", "  default:", "    packages:", f"      {platform}:"):
        if head not in lines:                                    # `in` reads the lines up to the head
            return []
    found = []
    for line in lines:
        item = ITEM.fullmatch(line)
        if not item:
            break
        found.append((item[1], item[2]))
    return found


def versions(lock: str, platform: str = "linux-64") -> dict[str, str]:
    """The version of each PyPI package of the default environment on one platform, as the lock's entry gives it.

    pixi puts a version in quotes where YAML would read a number, as in '3.7'; the quotes are not part of it.
    """
    entries = {url: (normal(name), version.strip("'\"")) for url, name, version in ENTRY.findall(lock)}
    return dict(entries[url] for kind, url in items(lock, platform) if kind == "pypi" and url in entries)


def python(lock: str) -> str:
    """The version of Python on linux-64, from the file name of its conda package: name-version-build."""
    for kind, url in items(lock, "linux-64"):
        if kind == "conda" and url.startswith("https://"):
            name, version, _build = url.rsplit("/", 1)[-1].rsplit("-", 2)
            if name == "python":
                return version
    return ""


def needs(text: str) -> list[tuple[str, str]]:
    """Each requirement of a requirements file: its name and what follows the name, such as ==2.4.6."""
    found = []
    for line in text.splitlines():
        need = NEED.fullmatch(line.split("#", 1)[0].strip())
        if need:
            found.append((normal(need[1]), need[2].replace(" ", "")))
    return found


def others(text: str) -> list[str]:
    """Each line of a requirements file that is not blank, a comment or a requirement of a name, as -r more.txt."""
    rows = (line.split("#", 1)[0].strip() for line in text.splitlines())
    return [row for row in rows if row and not NEED.fullmatch(row)]


def differences(requirements: str, runtime: str, lock: str) -> list[str]:
    """What is not as the lock has it on linux-64, each as one text.

    A line that is not a pin to the version of the lock, a package of BINDER with no pin, and a Python in runtime.txt
    that is not the one of the lock.
    """
    held = versions(lock)
    found = [f"{name}{spec}: the lock has {held.get(name, 'no such package')}"
             for name, spec in needs(requirements) if spec != f"=={held.get(name)}"]
    found += [f"{row}: not a pin of a name to a version" for row in others(requirements)]
    named = {name for name, _ in needs(requirements)}
    found += [f"{name}: no pin, the lock has {held.get(name, 'no such package')}" for name in sorted(BINDER - named)]
    if runtime.strip() != "python-" + ".".join(python(lock).split(".")[:2]):   # Binder takes python-X.Y
        found.append(f"{runtime.strip()}: the lock has python {python(lock) or 'none'}")
    return found


def copy(tmp_path: Path, path: Path, text: str) -> str:
    """The text of a copy of `path` in tmp_path that holds `text`, read back from there."""
    (tmp_path / path.name).write_text(text, encoding="utf-8")
    return read(tmp_path / path.name)


def added(requirements: str, lock: str) -> set[str]:
    """The differences of a changed requirements text that the real .binder/requirements.txt does not have."""
    runtime = read(RUNTIME)
    return set(differences(requirements, runtime, lock)) - set(differences(read(REQUIREMENTS), runtime, lock))


def entry_of(lock: str, name: str, platform: str) -> str:
    """The entry of the lock for one PyPI package on one platform: its lines pypi, name and version."""
    urls = {url for kind, url in items(lock, platform) if kind == "pypi"}
    return next(entry[0] for entry in ENTRY.finditer(lock) if entry[1] in urls and normal(entry[2]) == name)


PINS = [line for line in read(REQUIREMENTS).splitlines() if NEED.fullmatch(line.split("#", 1)[0].strip())]
NAMES = [name for name, _ in needs(read(REQUIREMENTS))]
FORMS = [pytest.param("{name}=={version}.1", id="newer"), pytest.param("{name}", id="unpinned"),
         pytest.param("{name}<9", id="a-bound"), pytest.param("{name} == 0", id="older")]
LINES = [pytest.param("-r more.txt", True, id="another-file"), pytest.param("-e .", True, id="editable"),
         pytest.param("--extra-index-url https://example.org/simple", True, id="an-index"),
         pytest.param("./wheels/qrisp.whl", True, id="a-path"), pytest.param("", False, id="blank"),
         pytest.param("   ", False, id="spaces"), pytest.param("# a comment", False, id="a-comment")]


def test_the_lock_is_read_on_both_platforms_and_holds_each_package_that_binder_installs():
    lock = read(LOCK)
    assert NAMES and python(lock).startswith("3.")
    for platform in ("linux-64", "osx-arm64"):
        assert set(NAMES) <= set(versions(lock, platform)), platform


def test_binder_pins_each_package_and_names_the_python_of_the_lock_on_linux():
    found = differences(read(REQUIREMENTS), read(RUNTIME), read(LOCK))
    assert found == [], ("pin these in .binder/ to the linux-64 versions of examples/qrisp/pixi.lock: "
                         + "; ".join(found))


@pytest.mark.parametrize("line", PINS)
@pytest.mark.parametrize("form", FORMS)
def test_a_requirement_that_differs_from_the_lock_is_found(tmp_path, line, form):
    lock, name = read(LOCK), NEED.fullmatch(line)[1]
    held = versions(lock)[normal(name)]
    change = form.format(name=name, version=held)
    text = copy(tmp_path, REQUIREMENTS, "".join(f"{change if row == line else row}\n"
                                                for row in read(REQUIREMENTS).splitlines()))
    [(changed, spec)] = needs(change)
    assert added(text, lock) == {f"{changed}{spec}: the lock has {held}"}


@pytest.mark.parametrize("name", sorted(BINDER))
def test_a_pin_taken_out_is_found(tmp_path, name):
    lock, rows = read(LOCK), read(REQUIREMENTS).splitlines()
    text = copy(tmp_path, REQUIREMENTS, "".join(f"{row}\n" for row in rows if [n for n, _ in needs(row)] != [name]))
    assert added(text, lock) == {f"{name}: no pin, the lock has {versions(lock)[name]}"}


@pytest.mark.parametrize("line, counts", LINES)
def test_a_line_that_is_not_blank_a_comment_or_a_pin_is_found(tmp_path, line, counts):
    text = copy(tmp_path, REQUIREMENTS, "".join(f"{row}\n" for row in [*read(REQUIREMENTS).splitlines(), line]))
    assert added(text, read(LOCK)) == ({f"{line}: not a pin of a name to a version"} if counts else set())


@pytest.mark.parametrize("quote", ["'", '"'])
def test_a_version_that_the_lock_writes_in_quotes_is_read_without_them(tmp_path, quote):
    lock, binder = read(LOCK), (read(REQUIREMENTS), read(RUNTIME))
    entry = entry_of(lock, "numpy", "linux-64")
    head, version = entry.rsplit(" ", 1)
    quoted = copy(tmp_path, LOCK, lock.replace(entry, f"{head} {quote}{version}{quote}", 1))
    assert versions(quoted)["numpy"] == version
    assert differences(*binder, quoted) == differences(*binder, lock)


@pytest.mark.parametrize("runtime", ["python-3.11", "python-3.13", "python-3", "python-3.12.0", ""])
def test_a_runtime_that_is_not_the_python_of_the_lock_is_found(tmp_path, runtime):
    lock = read(LOCK)
    found = differences(read(REQUIREMENTS), copy(tmp_path, RUNTIME, f"{runtime}\n"), lock)
    assert f"{runtime}: the lock has python {python(lock)}" in found


@pytest.mark.parametrize("name", ["numpy", "scipy", "matplotlib"])       # a wheel of its own on each platform
def test_a_version_that_moves_in_the_lock_counts_on_linux_only(tmp_path, name):
    lock, binder = read(LOCK), (read(REQUIREMENTS), read(RUNTIME))
    for platform, counts in (("linux-64", True), ("osx-arm64", False)):
        entry = entry_of(lock, name, platform)
        moved = copy(tmp_path, LOCK, lock.replace(entry, f"{entry}.1", 1))
        assert (differences(*binder, moved) != differences(*binder, lock)) is counts, platform
