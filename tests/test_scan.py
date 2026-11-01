"""A scan of every text: no em or en dash, excluded SDK, private path or name, and no date in public text.

The banned strings are held as SHA-256 digests, so that this file holds none of them and none can be read from it.
"""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEAD = 5                                      # the first characters, hashed apart to find where to look
BANNED = [  # each banned string in lower case: the digest of its head, of all of it, and its length
    ("bda050585a00f0f6cb502350559d75532ae3b244c9498b996e7c5df2d98dfc8d",
     "bda050585a00f0f6cb502350559d75532ae3b244c9498b996e7c5df2d98dfc8d", 1),
    ("d4f85d36757c12f0c6dab57721287f327efbfc46ea8c0f820301067f8627fc0f",
     "d4f85d36757c12f0c6dab57721287f327efbfc46ea8c0f820301067f8627fc0f", 1),
    ("8b2908b76655c73b7309eb75dbe881305501ebc8da7b31d7c1ecd7e1f4deb99e",
     "f44b167c73702f9ded3f9d5048cc365589ceab20fb4bce706af0b6a0f9dc6c74", 6),
    ("c9ffce190f1d5c1f64cfc8abc900d97d6ede620346a7ce44a3aa61e67d399711",
     "3e44fb009899c0f900c1e74cd803b171d70a5d799d2cc933898d78e8d5fc17ca", 7),
    ("3f502fbb24b520d62296ba7e265b06e5bf81e7246503d216b0584c6c21b5a8e1",
     "9d3dca20033b8aab1b0eb96014a9b88a7ad7ad5d13091c7bed75f8d33bf91a34", 8),
    ("d5d6b34ec24d82e6cc0bab41f4c6e87775b1b599ac2e100c8394aa6c5d90d438",
     "bc1a87c673f6a3aa784f013dea60ded303d36a32e717fb422be5c75e30ed627a", 17),
    ("27dbc006c8f619663e2a9cd150182d60f5f91eb779f70311f5b804bcf89f74f8",
     "6d543a7d3ef37d28b601c88fd9cc2e45752d3dedd11d96e7382f0b896dec2ee0", 13),
    ("7a65dd8d859c42b6297b29c1099dd6ebecba64186868a03fd61434b6f500206a",
     "431cb1cf116d952a842b9cb069a3fa45819d7240dcad68258a7b47dab83ed2dd", 9),
    ("be879f7549cc80c04241dcfd933c6278c3a711ddc530961071f62c57324d6a9e",
     "be879f7549cc80c04241dcfd933c6278c3a711ddc530961071f62c57324d6a9e", 5),
    ("cced28c6dc3f99c2396a5eaad732bf6b28142335892b1cd0e6af6cdb53f5ccfa",
     "acb4e2401d9756b7bbe3d21b21da9b1b2f1ffaf64ca3373e7c5db4f1ea96ff7a", 10),
    ("327d2d3e899b5194cfdcf813f5ec6597e73b9e4024d6196d2f8b673031da870d",
     "579cfa474ba435d396c61ad63894a48f28f95624738201d9e49ffaa061194d4e", 11),
]
FIRST_NAME = BANNED[8][1]
SUFFIXES = {".py", ".md", ".toml", ".json", ".qasm", ".txt", ".html", ".css", ".yml", ".bat", ".svg"}

AUTHOR_FIELDS = {"pyproject.toml", "CITATION.cff"}          # they name the author on purpose

PUBLIC = {"content", "README.md", "src", "examples"}        # first path parts of public text; tests need time stamps
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December")
NAMES = "|".join(MONTHS + tuple(month[:3] for month in MONTHS if month != "May") + ("Sept",))
DAY = r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?"
DATE = re.compile(rf"{DAY}(?:\s+of)?\s+(?:{NAMES})\b"                                # a day and a month name
                  rf"|\b(?:{NAMES})\.?,?\s+(?:{DAY}(?!\d)|(?:1[89]|2\d)\d\d(?!\d))"  # a month name and a day or year
                  r"|(?<!\d)\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])(?!\d)"   # an ISO date
                  r"|(?<!\d)(?:19|20)\d\d(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])T\d{4}"  # a stamp of a file name
                  r"|(?<![\w.,:\[])20[1-3]\d(?!\w|[.,]\d)")                         # a year, not a number in code
COPYRIGHT = re.compile(r"^Copyright\b.*", re.MULTILINE)     # a line of a licence notice: licence data


def files():
    for top in ("src", "tests", "content", "examples", ".github"):
        yield from (p for p in (ROOT / top).rglob("*") if p.suffix in SUFFIXES and p.is_file())
    for name in ("README.md", "pyproject.toml", "LICENSE", "LICENSE.code", "CITATION.cff", ".gitignore",
                 ".gitattributes"):
        if (ROOT / name).exists():
            yield ROOT / name


def allowed(path: Path) -> set:
    """The banned words a file may hold: the first name in the author fields, and nothing else."""
    return {FIRST_NAME} if path.parent == ROOT and path.name in AUTHOR_FIELDS else set()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def heads(texts) -> dict[str, str]:
    """Each head of a banned string that the texts hold, by its digest."""
    sizes = {min(HEAD, size) for _, _, size in BANNED}
    digests = {_sha(part): part for part in {text[i:i + k] for text in texts for k in sizes
                                             for i in range(len(text) - k + 1)}}
    return {head: digests[head] for head, _, _ in BANNED if head in digests}


def banned(text: str, found: dict[str, str]) -> set[str]:
    """The digests of the banned strings that a text in lower case holds."""
    return {whole for head, whole, size in BANNED if head in found
            and any(_sha(text[m.start():m.start() + size]) == whole
                    for m in re.finditer(f"(?={re.escape(found[head])})", text))}


def dates(text: str) -> list[str]:
    return [m.group() for m in DATE.finditer(COPYRIGHT.sub("", text))]


def test_no_banned_text():
    texts = {path: path.read_text(encoding="utf-8").lower() for path in files()}
    found = heads(texts.values())
    assert sorted((str(path.relative_to(ROOT)), word) for path, text in texts.items()
                  for word in banned(text, found) - allowed(path)) == []


def test_only_the_author_fields_may_hold_the_first_name():
    assert allowed(ROOT / "pyproject.toml") == allowed(ROOT / "CITATION.cff") == {FIRST_NAME}
    assert allowed(ROOT / "README.md") == allowed(ROOT / "LICENSE.code") == set()
    assert allowed(ROOT / "src" / "pyproject.toml") == set()


def test_no_date_in_public_text():
    """No date a page was read, no date of a site's answer, no release date of a version, no dated observation."""
    public = [p for p in files() if p.relative_to(ROOT).parts[0] in PUBLIC]
    assert {p.relative_to(ROOT).parts[0] for p in public} == PUBLIC
    found = [(str(p.relative_to(ROOT)), date) for p in public for date in dates(p.read_text(encoding="utf-8"))]
    assert found == []


def test_the_date_rule_finds_each_form_of_a_date_and_no_other_text():
    """The dates are built from parts here, so that this file holds none; the other texts are not dates."""
    day, month, year = "7", MONTHS[9], str(2000 + 26)
    forms = [f"read {day} {month} {year}", f"the {day}th of {month}", f"{day} {month[:3]}", f"({month} {year})",
             f"{month[:3]}. {year}", f"{month} {day}, {year}", "-".join((year, "10", "07")),
             "-".join((year, "10", "07T10:00:00+00:00")), "".join((year, "10", "07", "T091500Z")),
             f"by the end of {year}.", f"({year})"]
    assert [form for form in forms if not dates(form)] == []
    plain = ['"Unknown job. May be expired."', "UTC+2 from 01:00 UTC on the last Sunday of March",
             "the hour that the October change repeats", "order 2 may be sent", "release 1.15.0",
             "at most 2000 operations", "3,000,000 shots times gates", "commit fa35d0e", "digest 2031fa0e", "0.2031 s"]
    assert {text: dates(text) for text in plain if dates(text)} == {}
    assert dates(f"Copyright (c) {year}, ENCCS and individual contributors.\nby {year}") == [year]
    assert dates(Path(__file__).read_text(encoding="utf-8")) == []
