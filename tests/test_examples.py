"""Every example passes the dry run, the example rules file loads, and the example circuits carry no comment."""

import json
import re
from pathlib import Path

import pytest
from fakes import places_in

from qdevices import config, dryrun, rulebook

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
MANIFESTS = sorted(EXAMPLES.glob("*/manifest.json"))
COMMENT =re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)


def comments(path: Path) -> str:
    """All comments of a circuit file (line, trailing and block, as qdevices.qasm finds them) as one line of text."""
    found = COMMENT.findall(path.read_text(encoding="utf-8"))
    bodies = (c[2:-2] if c.startswith("/*") else c[2:] for c in found)
    return " ".join(" ".join(bodies).split())


def test_there_is_an_example_of_each_kind():
    names = {p.parent.name for p in MANIFESTS}
    for site in ("euroqexa", "vlq", "piastq"):
        assert {f"{site}-one-qubit", f"{site}-bell"} <= names
    assert "euroqexa-three-jobs" in names


def test_each_starter_example_names_its_source():
    starters = {"euroqexa-ghz", "euroqexa-inverse", "vlq-ghz", "piastq-native"}
    sources = {p.parent.name: json.loads(p.read_text(encoding="utf-8")).get("source") for p in MANIFESTS}
    assert starters <= set(sources)
    assert all(sources[name] for name in starters)


@pytest.mark.parametrize("manifest", MANIFESTS, ids=lambda p: p.parent.name)
def test_each_example_passes_the_dry_run(tmp_path, manifest):
    conf = config.load(EXAMPLES / "qdevices.toml")
    out = []
    assert dryrun.dry_run(manifest, cfg=conf, places=places_in(tmp_path), say=out.append) == 0, out


@pytest.mark.parametrize("name", ["vlq-bell", "vlq-ghz"])
def test_a_vlq_example_addresses_the_resonator_of_the_table_it_takes(name):
    """The table the files take: QB1 to QB24 at 0 to 23, the resonator at 24; the qubit comes first."""
    text = next((EXAMPLES / name).glob("*.qasm")).read_text(encoding="utf-8")
    assert "qubit[25] q;" in text
    pairs = re.findall(r"^(?:move|cz) q\[(\d+)\], q\[(\d+)\];", text, re.MULTILINE)
    assert pairs and all(r == "24" and int(q) < 24 for q, r in pairs)
    assert all(int(q) < 24 for q in re.findall(r"measure q\[(\d+)\]", text))


def test_the_vlq_page_says_which_table_the_examples_take_and_the_check_of_the_app():
    """What a user needs, in the manual: the table the VLQ examples take, as their assumption, and the check."""
    text = " ".join((EXAMPLES.parent / "content" / "vlq.md").read_text(encoding="utf-8").split())
    for words in ("The example files `vlq-bell` and `vlq-ghz` take QB1 to QB24 at 0 to 23 and the resonator COMPR1 "
                  "at 24", "the app checks each text against the table of the day",
                  "A text that does not fit the table stops the call before the metered job is made"):
        assert words in text, words


def test_the_example_circuits_carry_no_comment():
    """What a circuit needs to say is in the manual, so a file is only its circuit."""
    texts = {p.relative_to(EXAMPLES).as_posix(): comments(p) for p in sorted(EXAMPLES.rglob("*.qasm"))}
    assert texts and {name: text for name, text in texts.items() if text} == {}


def test_the_example_rules_file_loads_and_judges():
    hooks, _ = rulebook.load(EXAMPLES / "rules_bell.py")
    job = {"name": "BELL", "shots": 100, "order": 2}
    assert hooks["after_result"](job, {"counts": {"00": 48, "11": 47, "01": 5}}, {})["passed"]
    assert not hooks["after_result"](job, {"counts": {"01": 90, "00": 10}}, {})["passed"]
