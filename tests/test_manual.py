"""G6: the manual has a page for each machine of the registry, in its toctree and in the list of the first page."""

from pathlib import Path

import pytest

from qdevices.sites import SITES

CONTENT = Path(__file__).resolve().parent.parent / "content"


def toctree(text: str, caption: str) -> list[str]:
    """The entries of the toctree of a page with this caption, in their order."""
    block = text.split(f":caption: {caption}\n", 1)[1].split("```", 1)[0]
    return [line.strip() for line in block.splitlines() if line.strip() and not line.strip().startswith(":")]


@pytest.mark.parametrize("name", list(SITES))
def test_the_page_of_each_machine_names_its_title_operator_token_variable_and_addresses(name):
    cls = SITES[name]
    text = (CONTENT / f"{name}.md").read_text(encoding="utf-8")
    assert text.splitlines()[0] == f"# {cls.profile.title} ({cls.profile.operator})"
    assert [word for word in (cls.token_env, *cls.addresses) if word not in text] == []


def test_the_first_page_lists_each_machine_and_its_toctree_holds_their_pages_in_registry_order():
    text = (CONTENT / "index.md").read_text(encoding="utf-8")
    assert toctree(text, "The sites") == list(SITES)
    listed = [f"**{cls.profile.title}** at {cls.profile.operator}" for cls in SITES.values()]
    assert [item for item in listed if item not in text] == []
