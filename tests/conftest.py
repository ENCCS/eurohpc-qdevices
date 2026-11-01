"""The fixtures of every test: the places, the fake clock, the signal handlers and the golden texts."""

import difflib
import re
import signal
from pathlib import Path

import pytest
from fakes import FakeClock, places_in

ROOT = Path(__file__).absolute().parent.parent       # the repository, as pytest found it
GOLDEN = ROOT / "tests" / "golden"
GOLDEN_NAME = re.compile(r"[a-z0-9_]+")
NUMBER = re.compile(r'"(device|inode|pid)": -?\d+')  # default json.dumps separators, as record.py writes
USED: dict[str, str] = {}                            # each golden name of this session: its test


@pytest.fixture
def places(tmp_path):
    return places_in(tmp_path)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture(autouse=True)
def signals():
    """Every test leaves the signal handlers as it found them."""
    earlier = {n: signal.getsignal(n) for n in (signal.SIGTERM, signal.SIGHUP)}
    yield
    for n, h in earlier.items():
        signal.signal(n, h)


# --------------------------------------------------------------------- the golden texts

def pytest_addoption(parser):
    parser.addoption("--golden", choices=("check", "write"), default="check",
                     help="check (the default): compare each golden text with tests/golden/NAME.txt; "
                          "write: write those files from the code as it is")


def masked(text: str, tmp_path: Path, masks: dict[str, str] | None = None) -> str:
    """The text with the paths, then each key of `masks`, then the device, inode and pid numbers masked.

    A key of `masks` is found after the paths are masked, so it holds <TMP> where it would hold the tmp path.
    """
    for place, mark in ((Path(tmp_path), "<TMP>"), (ROOT, "<ROOT>"), (Path.home(), "<HOME>")):
        for form in (str(place.resolve()), str(place)):
            if len(form) > 1:                        # never the root folder alone
                text = text.replace(form, mark)
    for key, value in (masks or {}).items():
        text = text.replace(key, value)
    return NUMBER.sub(r'"\1": "<N>"', text)


def differences(name: str, expected: str, text: str) -> str:
    """A unified diff of the golden file and the text of this run."""
    found = difflib.unified_diff(expected.splitlines(keepends=True), text.splitlines(keepends=True),
                                 f"tests/golden/{name}.txt", "this run")
    return "".join(line if line.endswith("\n") else line + "\n" for line in found)


@pytest.fixture
def golden(request, tmp_path):
    """golden(name, text, masks=None): the masked text against tests/golden/NAME.txt, or written there."""
    write = request.config.getoption("golden") == "write"

    def compare(name: str, text: str, masks: dict[str, str] | None = None) -> None:
        if not GOLDEN_NAME.fullmatch(name):
            pytest.fail(f"the golden name {name!r} is not of [a-z0-9_]", pytrace=False)
        owner = USED.setdefault(name, request.node.nodeid)
        if owner != request.node.nodeid:
            pytest.fail(f"the golden {name} is used by {owner} and by {request.node.nodeid}: give each case a "
                        "name of its own", pytrace=False)
        path, text = GOLDEN / f"{name}.txt", masked(text, tmp_path, masks)
        if write:
            GOLDEN.mkdir(exist_ok=True)
            path.write_bytes(text.encode("utf-8"))
            return
        if not path.is_file():
            pytest.fail(f"there is no golden tests/golden/{name}.txt: write it with --golden=write on the code "
                        "it pins, and read it by eye", pytrace=False)
        expected = path.read_bytes().decode("utf-8")
        if text != expected:
            pytest.fail(f"the text is not the golden {name}:\n{differences(name, expected, text)}", pytrace=False)

    return compare
