"""G1: no code of the app outside sites/ holds a word of a machine; such a fact is read from the class of its site.

The words come from the registry when the test runs, with the words of the routes that no fact of a class holds.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

from qdevices.sites import SITES

SRC = Path(__file__).resolve().parent.parent / "src" / "qdevices"
ROUTE_WORDS = ("LEXIS", "HEAppE", "MQSS", "IT4I", "MyAccessID", "PSNC", "Munich", "USER_JWT_PWD")


def site_words() -> set[str]:
    """Each word of a site: its name, title, operator, token variable, machines and hosts, and the route words."""
    words = set(ROUTE_WORDS)
    for name, cls in SITES.items():
        words |= {name, cls.profile.title, cls.profile.operator, cls.token_env, cls.default_machine,
                  *cls.profile.older_machines, *(urlsplit(address).hostname for address in cls.addresses)}
    return words - {None, ""}


def finder(words: set[str]) -> re.Pattern[str]:
    """Any of the words in any case, with no letter or digit before it and no letter after it."""
    alternatives = "|".join(map(re.escape, sorted(words, key=len, reverse=True)))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alternatives})(?![A-Za-z])", re.IGNORECASE)


def found_in(folder: Path, words: set[str], *, skip: Path | None = None) -> list[str]:
    """path:line:word for each word in the .py files below a folder, comments and docstrings included."""
    find = finder(words)
    return [f"{path.relative_to(SRC.parent.parent)}:{number}:{hit.group()}"
            for path in sorted(folder.rglob("*.py")) if skip is None or skip not in path.parents
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            for hit in find.finditer(line)]


def test_the_finder_takes_a_whole_word_in_any_case():
    find = finder({"vlq", "Piast-Q"})
    texts = ("is_vlq = 1", "# VLQ jobs", "vlqs = 1", "my2vlq", "piast-q2", "PIAST-Q.")
    assert [bool(find.search(text)) for text in texts] == [True, True, False, False, True, True]


def test_the_scan_finds_the_name_of_each_site_in_the_site_modules():
    found = found_in(SRC / "sites", site_words())
    assert set(SITES) <= {line.rsplit(":", 1)[1].lower() for line in found}


def test_no_code_outside_sites_holds_a_word_of_a_machine():
    found = found_in(SRC, site_words(), skip=SRC / "sites")
    assert found == [], ("a word of a machine outside sites/: read it from a fact of its class, as "
                         "SITES[name].profile.<fact> inside a function, or move the code into the site module:\n"
                         + "\n".join(found))
