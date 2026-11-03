"""The two pictures of each example folder, as files: present, small, shown by the README, and with no version or date.

Python alone; examples/tools/write_pictures.py draws them: `pixi run --manifest-path examples/qrisp/pixi.toml pictures`.
"""

import json
import re
import struct
import sys
from pathlib import Path

import pytest

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
sys.path.insert(0, str(EXAMPLES / "tools"))
from overview import example_folders  # noqa: E402
from readme import DRAWN  # noqa: E402

FOLDERS = example_folders(EXAMPLES)
NAMES = [f.relative_to(EXAMPLES).as_posix() for f in FOLDERS]
PICTURES = ("circuit.png", "outcomes.png")
SIGNATURE = b"\x89PNG\r\n\x1a\n"
EACH, ALL, LONGEST = 80 * 1024, 3 * 1024 * 1024, 1200   # bytes, bytes, pixels


def chunks(data: bytes) -> list:
    """The (type, body) of each chunk of a PNG file."""
    out, at = [], len(SIGNATURE)
    while at < len(data):
        size, kind = struct.unpack(">I4s", data[at:at + 8])
        out.append((kind.decode("ascii"), data[at + 8:at + 8 + size]))
        at += 12 + size
    return out


@pytest.mark.parametrize("folder", FOLDERS, ids=NAMES)
def test_each_folder_holds_both_pictures_as_small_png_files(folder):
    for name in PICTURES:
        data = (folder / name).read_bytes()
        assert data.startswith(SIGNATURE), name
        assert len(data) < EACH, (name, len(data))
        found = chunks(data)
        assert found[0][0] == "IHDR" and found[-1][0] == "IEND", name
        assert max(struct.unpack(">II", found[0][1][:8])) <= LONGEST, name


@pytest.mark.parametrize("folder", FOLDERS, ids=NAMES)
def test_no_picture_holds_a_version_a_date_or_any_text(folder):
    for name in PICTURES:
        kinds = {kind for kind, _ in chunks((folder / name).read_bytes())}
        assert not kinds & {"tEXt", "iTXt", "zTXt", "tIME"}, (name, kinds)


def test_all_the_pictures_together_stay_small():
    assert sum((folder / name).stat().st_size for folder in FOLDERS for name in PICTURES) < ALL


@pytest.mark.parametrize("folder", FOLDERS, ids=NAMES)
def test_each_readme_shows_both_pictures_under_its_first_diagram_and_lists_them(folder):
    text = (folder / "README.md").read_text(encoding="utf-8")
    shown = [text.index(f"]({name})") for name in PICTURES]
    assert text.index("```mermaid") < shown[0] < shown[1] < text.index("**What a perfect machine gives:**")
    for name in PICTURES:
        assert text.count(f"]({name})") == 1 and f"| `{name}` |" in text, name


@pytest.mark.parametrize("folder", FOLDERS, ids=NAMES)
def test_each_readme_says_which_job_is_drawn_and_shows_the_machine_only_if_it_ran(folder):
    text = (folder / "README.md").read_text(encoding="utf-8")
    jobs, name = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["jobs"], folder.relative_to(
        EXAMPLES).as_posix()
    assert ("The circuit of the first job as" in text) == (len(jobs) > 1 and name not in DRAWN)
    assert ("The circuit of the job as" in text) == (len(jobs) == 1)
    if name in DRAWN:
        assert f"The circuit of the job {DRAWN[name]} as" in text and DRAWN[name] in [job["name"] for job in jobs]
    machine = "and one run on the machine, with a bar of one shot error each way"
    assert (machine in text) == (folder / "results.json").exists()


def test_the_job_drawn_is_the_one_the_readme_above_it_describes():
    assert DRAWN == {"hamiltonian/state_transfer": "MAIN", "euroqexa-three-jobs": "BELL"}


def test_the_task_that_draws_them_is_in_the_emulators_workspace():
    toml = (EXAMPLES / "qrisp" / "pixi.toml").read_text(encoding="utf-8")
    assert re.search(r"^pictures = .*examples/tools/write_pictures\.py", toml, re.MULTILINE)
