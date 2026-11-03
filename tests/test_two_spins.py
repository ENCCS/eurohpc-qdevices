"""examples/hamiltonian/two_spins: the texts, the counts, the numbers its pages quote, its notebook and its links."""

import hashlib
import json
import re
import sys
from math import sqrt
from pathlib import Path

import pytest
from test_scan import banned, dates, heads, text_of

from qdevices.paths import Places

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
HERE = EXAMPLES / "hamiltonian" / "two_spins"
sys.path[:0] = [str(HERE), str(EXAMPLES / "tools")]
import dry_run  # noqa: E402
from circuit import Circuit, circuit_of  # noqa: E402
from machine import SameLoss, reads  # noqa: E402
from trotter import Steps  # noqa: E402

MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
JOBS = {job["name"]: job for job in MANIFEST["jobs"]}
SENT_STEPS16 = "558778961097b829170c129452894bb69d12048f3162c2de2e80a90baedd167c"   # the digest of the text that ran
NOTEBOOK = HERE / "two_spins.ipynb"
LINK = re.compile(r"\]\(([^)#]+)\)")


def perfect(name: str) -> dict:
    return circuit_of(HERE / JOBS[name]["file"]).shares()


def test_each_text_has_the_sha256_of_the_manifest():
    for job in MANIFEST["jobs"]:
        assert hashlib.sha256((HERE / job["file"]).read_bytes()).hexdigest() == job["sha256"], job["name"]
    assert MANIFEST["site"] == "euroqexa" and MANIFEST["project"] == "MY-PROJECT"
    assert [(job["order"], job["name"], job["shots"]) for job in MANIFEST["jobs"]] == [(1, "STEPS5", 1000),
                                                                                       (2, "STEPS16", 1000)]


def test_the_texts_are_those_that_ran():
    assert (HERE / "STEPS5.qasm").read_bytes() == (EXAMPLES / "qrisp" / "ising2" / "ISING2.qasm").read_bytes()
    assert JOBS["STEPS16"]["sha256"] == SENT_STEPS16


def test_the_counts_are_those_of_the_runs_and_sum_to_the_shots():
    read = reads(HERE)
    assert set(read) == set(JOBS)
    assert all(job.shots == JOBS[name]["shots"] for name, job in read.items())
    ising2 = json.loads((EXAMPLES / "qrisp" / "ising2" / "results.json").read_text(encoding="utf-8"))["ISING2"]
    assert read["STEPS5"].counts == ising2
    assert read["STEPS16"].counts == {"00": 113, "01": 53, "10": 45, "11": 789}


def test_the_sizes_and_the_perfect_shares_the_pages_quote():
    five, sixteen = (circuit_of(HERE / JOBS[n]["file"]) for n in ("STEPS5", "STEPS16"))
    assert (len(five.ops), five.two_qubit, len(sixteen.ops), sixteen.two_qubit) == (45, 10, 144, 32)
    assert round(perfect("STEPS5")["11"], 3) == 0.866 and round(perfect("STEPS16")["11"], 3) == 0.877
    assert round(perfect("STEPS5")["01"], 3) == round(perfect("STEPS5")["10"], 3) == 0.013
    assert round(perfect("STEPS16")["01"], 4) == 0.0001
    assert round(perfect("STEPS5")["01"] + perfect("STEPS5")["10"], 3) == 0.026


def test_the_text_in_python_alone_gives_the_shares_of_the_text_of_qrisp():
    ours = Circuit.of_text(Steps(5).text()).shares()
    assert max(abs(ours[key] - perfect("STEPS5")[key]) for key in ours) < 1e-12
    assert Circuit.of_text(Steps(16).text()).two_qubit == 32


def test_the_reading_and_the_simple_model_the_notebook_quotes():
    read = reads(HERE)
    five, sixteen = read["STEPS5"], read["STEPS16"]
    assert (round(five.error("11"), 3), round(sixteen.error("11"), 3)) == (0.013, 0.013)
    assert round(sqrt(five.error("11") ** 2 + sixteen.error("11") ** 2), 3) == 0.018
    assert round(perfect("STEPS5")["11"] - five.share("11"), 3) == 0.083
    assert round(five.share("01") + five.share("10"), 3) == 0.122
    model = SameLoss(perfect("STEPS5")["11"], five.share("11"), 10)
    assert round(model.kept, 3) == 0.986 and round(model.share(perfect("STEPS16")["11"], 32), 2) == 0.64
    assert round((sixteen.share("11") - model.share(perfect("STEPS16")["11"], 32)) / sixteen.error("11")) == 11
    assert model.share(perfect("STEPS5")["11"], 10) == pytest.approx(five.share("11"))
    loose = [SameLoss(perfect("STEPS5")["11"], five.share("11"), 10, readout).share(perfect("STEPS16")["11"], 32)
             for readout in (0.97, 0.95, 0.93)]
    assert [round(sixteen.share("11") - share, 2) for share in loose] == [0.12, 0.10, 0.08]
    assert [round((sixteen.share("11") - share) / sixteen.error("11")) for share in loose] == [9, 8, 6]


def test_the_chain_of_the_tutorial_read_as_the_notebook_says():
    folder = EXAMPLES / "hamiltonian" / "state_transfer"
    chain = {job["name"]: job for job in json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"]}
    counts = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    assert (chain["STEPS4"]["two_qubit"], chain["STEPS8"]["two_qubit"]) == (18, 34)
    assert (counts["STEPS4"]["100"] / 1000, counts["STEPS8"]["100"] / 1000) == (0.474, 0.190)


def test_the_folder_passes_its_dry_run_and_writes_nothing(tmp_path, monkeypatch, capsys):
    places = Places(records=tmp_path / "r", reads=tmp_path / "s", state=tmp_path / "t", config=tmp_path / "none.toml")
    monkeypatch.setattr(Places, "default", classmethod(lambda cls: places))
    assert dry_run.main([str(HERE / "manifest.json")]) == 0
    assert "This dry run uses examples/qdevices.toml." in capsys.readouterr().out
    assert not any(place.exists() for place in (places.records, places.reads, places.state))


def test_the_notebook_holds_its_outputs_and_no_error():
    book = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    code = [c for c in book["cells"] if c["cell_type"] == "code"]
    assert code and all(c["outputs"] for c in code[1:])
    assert not [o for c in code for o in c["outputs"] if o["output_type"] == "error"]
    assert book["metadata"]["mystnb"] == {"execution_mode": "off"}
    assert not [c for c in book["cells"] if "execution" in c["metadata"]]
    assert len({c["id"] for c in book["cells"]}) == len(book["cells"])


def test_the_notebook_is_public_text_and_needs_no_app_and_no_token():
    book = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    sources = "".join("".join(c["source"]) for c in book["cells"])
    text = text_of(NOTEBOOK)
    assert not dates(text) and not banned(text.lower(), heads([text.lower()]))
    for word in ("getpass", "import qdevices", "from qdevices", "advantage", "safety"):
        assert word not in sources, word
    assert chr(0x2014) not in sources and chr(0x2013) not in sources
    assert "urlpath=doc/tree/examples/hamiltonian/two_spins/two_spins.ipynb" in sources


def links(path: Path) -> list:
    return [link for link in LINK.findall(path.read_text(encoding="utf-8")) if "://" not in link]


@pytest.mark.parametrize("page", [HERE / "README.md", NOTEBOOK, EXAMPLES / "hamiltonian" / "README.md"],
                         ids=lambda p: p.relative_to(EXAMPLES).as_posix())
def test_each_link_of_a_page_leads_to_a_file(page):
    assert links(page)
    assert [link for link in links(page) if not (page.parent / link).exists()] == []


def test_the_pages_above_point_to_the_short_start():
    top = (EXAMPLES / "hamiltonian" / "README.md").read_text(encoding="utf-8")
    assert "(two_spins/README.md)" in top and "| `two_spins/` |" in top
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    assert "(two_spins.ipynb)" in readme and readme.count("two_spins/two_spins.ipynb") == 2   # the top and Emulate it
    front = (EXAMPLES / "README.md").read_text(encoding="utf-8")
    assert "(hamiltonian/two_spins/README.md)" in front and "examples/hamiltonian/two_spins/two_spins.ipynb" in front
    for name in ("two_spins.ipynb", "spins.py", "by_qrisp.py", "trotter.py", "machine.py", "write_two_spins.py",
                 "STEPS5.qasm", "STEPS16.qasm", "results.json"):
        assert f"| `{name}` |" in readme and (HERE / name).exists(), name
