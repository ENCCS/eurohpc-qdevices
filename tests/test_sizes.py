"""The size ratchet: no file of src/ or examples/ over 200 lines, and no function or method over 25 lines.

Offenders are listed in tests/golden/sizes.txt; a listed line no longer needed fails, so the list only shrinks.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LISTED = ROOT / "tests" / "golden" / "sizes.txt"
FILE_LINES, FUNCTION_LINES = 200, 25
ROW = re.compile(r"(\S+::\S+) ([0-9]+)")
DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)


def length(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """The lines of a def, from the def to its last line, less a docstring that is its first statement."""
    first = node.body[0]
    doc = isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str)
    return node.end_lineno - node.lineno + 1 - (first.end_lineno - first.lineno + 1 if doc else 0)


def functions(node: ast.AST, outer: tuple = ()):
    """(qualname, length) of each function and method below a node, nested ones too, in the order of the text."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, DEFS):
            yield ".".join((*outer, child.name)), length(child)
        named = isinstance(child, (*DEFS, ast.ClassDef))
        yield from functions(child, (*outer, child.name) if named else outer)


def offenders() -> dict[str, int]:
    """Each file over FILE_LINES lines and each function over FUNCTION_LINES, by "path::qualname", with its length."""
    found: dict[str, int] = {}
    for path in sorted(p for top in ("src", "examples") for p in (ROOT / top).rglob("*.py")):
        text, where = path.read_text(encoding="utf-8"), path.relative_to(ROOT).as_posix()
        if len(text.splitlines()) > FILE_LINES:
            found[f"{where}::<module>"] = len(text.splitlines())
        for name, lines in functions(ast.parse(text, filename=str(path))):
            key = f"{where}::{name}"
            if lines > FUNCTION_LINES:
                found[key] = max(lines, found.get(key, 0))      # a name given twice: the longer def
    return found


def listed() -> tuple[dict[str, int], list[str]]:
    """The offenders of the list by "path::qualname", with their lengths, and the lines that are not of that form."""
    rows = LISTED.read_text(encoding="utf-8").splitlines() if LISTED.is_file() else []
    matched = {row: ROW.fullmatch(row) for row in rows}
    return {m[1]: int(m[2]) for m in matched.values() if m}, [row for row, m in matched.items() if m is None]


def test_the_length_of_a_def_leaves_out_its_docstring_and_its_decorators():
    text = ('@decorated\ndef f():\n    """Two lines\n    of docstring."""\n    x = 1\n    return x\n\n\n'
            "class C:\n    def g(self):\n        def h():\n            pass\n        return h\n")
    assert list(functions(ast.parse(text))) == [("f", 3), ("C.g", 4), ("C.g.h", 2)]


def test_no_file_or_function_is_over_its_limit_unless_it_is_listed(pytestconfig):
    now = offenders()
    if pytestconfig.getoption("golden") == "write":
        LISTED.parent.mkdir(exist_ok=True)
        LISTED.write_text("".join(sorted(f"{key} {lines}\n" for key, lines in now.items())), encoding="utf-8")
        return
    allowed, malformed = listed()
    faults = [f"{row!r} in tests/golden/sizes.txt is not a line 'path::qualname length'" for row in malformed]
    if not LISTED.is_file():
        faults.append("tests/golden/sizes.txt is missing: write it with --golden=write on the code it pins")
    for key, lines in sorted(now.items()):
        if key not in allowed:
            faults.append(f"{key} has {lines} lines, over the limit and not listed: make it shorter")
        elif lines > allowed[key]:
            faults.append(f"{key} has {lines} lines, more than the {allowed[key]} it is listed with")
    faults += [f"{key} is no longer over the limit: delete its line from tests/golden/sizes.txt"
               for key in sorted(allowed) if key not in now]
    assert faults == []
