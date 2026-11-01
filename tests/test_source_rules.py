"""Rules of the source that hold while the code moves.

No new broad handler may sit between a stop and the loop; one base.py only, as test_sites.py passes over each.
The sites are the lower layer: the app reaches a machine only through the registry, read when a function runs.
"""

import ast
import json
import sys
from pathlib import Path

import pytest

from qdevices import record
from qdevices.runner.stop import StopKind, Stopped
from qdevices.sites import SITES

ROOT = Path(__file__).resolve().parent.parent
CLIENT_FILE = "src/qdevices/sites/base.py"
BROAD_NAMES = {"Exception", "BaseException"}
SITES_DIR = "src/qdevices/sites/"
OPEN_TO_ALL = ("qdevices.sites", "qdevices.sites.base", "qdevices.sites.protocol", "qdevices.sites.facts")
# What a module under sites/ may import of the app; each ends in a dot, as the name it is tested against does.
BELOW_SITES = ("qdevices.sites.", "qdevices.qasm.", "qdevices.clock.", "qdevices.layout.", "qdevices.values.")
UNPICKLERS = {"load", "loads", "Unpickler"}       # of the standard pickle: only the restricted reader may use them
# Each except clause that catches Exception, as (file, enclosing function); a wave that moves one edits it here.
BROAD = [
    ("src/qdevices/rulebook.py", "load"),                 # the code of a rules file: any error of it refuses the call
    ("src/qdevices/runner/hooks.py", "_verdicts_of"),     # a user hook that raises gives a failed verdict
    ("src/qdevices/runner/loop.py", "Loop._broken"),      # the lines of an error of the program, if they can be written
    ("src/qdevices/runner/loop.py", "Loop.run"),          # an error of the program: its stop line, then exit 3
    ("src/qdevices/runner/loop.py", "Loop.run"),          # the last write of a "submitted" line, before the close
    ("src/qdevices/sites/pickle_reader.py", "loads"),     # a malformed pickle is a file that cannot be read
    ("src/qdevices/sites/vlq/wire.py", "token_expiry"),   # a token whose expiry cannot be read has none
]
CATCH_A_STOP = {"Stopped", "BaseException"}       # the names of a clause that catches a stop; a bare clause does too
# Each member of StopKind: its name, its text on a stop line, and the exit code of the call it ends.
STOP_KINDS = [
    ("READ", "read", 1),
    ("CHECK", "check", 1),
    ("PREPARE", "prepare", 1),
    ("LOST", "lost", 1),
    ("STATUS_ERROR", "status_error", 1),
    ("RESULT_ERROR", "result_error", 1),
    ("RESULT_EXPIRED", "result_expired", 1),
    ("SUBMIT_UNKNOWN", "submit_unknown", 1),
    ("UNKNOWN", "unknown", 2),
    ("RULE", "rule", 2),
    ("TIMEOUT", "timeout", 2),
    ("ERROR", "error", 3),
    ("INTERRUPT", "interrupt", 130),
]


def sources() -> list[tuple[str, ast.Module]]:
    """Each .py file under src/, by its path from the repository root, with its tree."""
    paths = sorted((ROOT / "src").rglob("*.py"))
    return [(p.relative_to(ROOT).as_posix(), ast.parse(p.read_text(encoding="utf-8"), filename=str(p)))
            for p in paths]


def client_calls(tree: ast.AST) -> list[int]:
    """The lines where code calls httpx.Client, by that name or by a name it is imported as."""
    names = {"httpx.Client"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {f"{a.asname}.Client" for a in node.names if a.name == "httpx" and a.asname}
        elif isinstance(node, ast.ImportFrom) and node.module == "httpx":
            names |= {a.asname or a.name for a in node.names if a.name == "Client"}
    return sorted(n.lineno for n in ast.walk(tree) if isinstance(n, ast.Call) and ast.unparse(n.func) in names)


def handlers(node: ast.AST, outer: tuple = ()):
    """(enclosing function, clause) of each except clause below a node, in the order of the text."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ExceptHandler):
            yield ".".join(outer) or "<module>", child
        named = isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        yield from handlers(child, (*outer, child.name) if named else outer)


def catches_exception(clause: ast.ExceptHandler) -> bool:
    """True when a clause catches Exception: by that name, in a tuple, as BaseException, or bare."""
    kinds = clause.type.elts if isinstance(clause.type, ast.Tuple) else [clause.type]
    return any(k is None or getattr(k, "id", getattr(k, "attr", None)) in BROAD_NAMES for k in kinds)


def catches_a_stop(clause: ast.ExceptHandler) -> bool:
    """True when a clause catches Stopped: by that name, in a tuple, as an attribute, as BaseException, or bare."""
    kinds = clause.type.elts if isinstance(clause.type, ast.Tuple) else [clause.type]
    return any(k is None or getattr(k, "id", getattr(k, "attr", None)) in CATCH_A_STOP for k in kinds)


def hides(node: ast.AST) -> bool:
    """True for a name, an attribute or a text that is a broad name or a stop."""
    text = node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None
    return getattr(node, "id", getattr(node, "attr", text)) in BROAD_NAMES | CATCH_A_STOP


def blind_spots(tree: ast.AST) -> list[int]:
    """The lines the clause finders cannot see: a suppress of a broad name or a stop, or another name for one."""
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and getattr(n.func, "id", getattr(n.func, "attr", "")) == "suppress":
            found += [n.lineno] if any(hides(m) for a in n.args for m in ast.walk(a)) else []
        elif isinstance(n, (ast.Assign, ast.AnnAssign, ast.NamedExpr)) and n.value is not None:
            found += [n.lineno] if any(hides(part) for part in ast.walk(n.value)) else []
        elif isinstance(n, (ast.Import, ast.ImportFrom)):       # suppress or a hidden name, imported as another
            found += [n.lineno for a in n.names if a.asname and (a.name == "suppress" or hides(ast.Name(a.name)))]
    return sorted(found)


def is_module(name: str) -> bool:
    """True for a module or package of src/ by its dotted name."""
    where = ROOT / "src" / Path(*name.split("."))
    return where.with_suffix(".py").is_file() or (where / "__init__.py").is_file()


def imports(path: str, tree: ast.AST) -> list[tuple[int, str]]:
    """(line, module) of each import of a file, made absolute; a module named in a from-import is one too."""
    package, found = list(Path(path).with_suffix("").parts[1:-1]), []     # the package the file is in
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            up = package[:len(package) - node.level + 1] if node.level else []
            base = ".".join([*up, node.module] if node.module else up)
            found.append((node.lineno, base))
            found += [(node.lineno, f"{base}.{a.name}") for a in node.names if is_module(f"{base}.{a.name}")]
    return sorted(found)


def reads_at_import(tree: ast.AST, name: str) -> list[int]:
    """The lines where a name, or an attribute of that name, is used when its module is imported, not in a call."""
    in_a_call = {id(node) for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
                 for part in (n.body if isinstance(n.body, list) else [n.body]) for node in ast.walk(part)}
    return sorted(n.lineno for n in ast.walk(tree)
                  if id(n) not in in_a_call and name in (getattr(n, "id", None), getattr(n, "attr", None)))


def unpickles(tree: ast.AST) -> list[int]:
    """The lines that reach the unpickler of the standard library, by the module or by a name imported from it."""
    names = {"pickle"} | {a.asname for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names
                          if a.name == "pickle"}
    found = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr in UNPICKLERS and ast.unparse(n.value) in names]
    return sorted(found + [n.lineno for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                           and n.module == "pickle" and {a.name for a in n.names} & UNPICKLERS])


def listed_events() -> set[str]:
    """The event names in the module docstring of record.py, read as test_older_names.py reads them."""
    listed = record.__doc__.split("Event names written by this app:")[1].split("\n\n")[0]
    return set(" ".join(listed.split()).strip(" .").split(", "))


def events_of(path: Path) -> list:
    """The event of each line of a record golden that is a JSON object, read as record.py reads a record."""
    found = []
    for row in path.read_bytes().decode("utf-8").split("\n"):
        try:
            line = json.loads(row)
        except ValueError:
            continue
        if isinstance(line, dict):
            found.append(line.get("event"))
    return found


def test_the_finders_see_each_form():
    text = ("import httpx as h\nfrom httpx import Client as C\n\n\nclass A:\n    def f(self):\n        h.Client()\n"
            "        C()\n        try:\n            pass\n        except (ValueError, Exception):\n            pass\n"
            "        except:\n            pass\n\n\ntry:\n    pass\nexcept BaseException:\n    pass\n"
            "except OSError:\n    pass\n")
    tree = ast.parse(text)
    assert client_calls(tree) == [7, 8]
    assert [(where, catches_exception(c)) for where, c in handlers(tree)] == [
        ("A.f", True), ("A.f", True), ("<module>", True), ("<module>", False)]


def test_only_sites_base_makes_an_http_client_and_no_other_module_is_named_base():
    trees = sources()
    assert [path for path, tree in trees if client_calls(tree)] == [CLIENT_FILE]
    assert [path for path, _ in trees if Path(path).name == "base.py"] == [CLIENT_FILE]


def test_no_site_class_has_a_name_that_holds_cancel():
    assert SITES
    assert [(cls.__name__, name) for cls in SITES.values() for name in dir(cls) if "cancel" in name.lower()] == []


def test_an_except_clause_that_catches_exception_stands_only_where_one_stands_today():
    found = [(path, where) for path, tree in sources() for where, clause in handlers(tree) if catches_exception(clause)]
    assert sorted(found) == sorted(BROAD)


def test_a_stop_derives_from_base_exception_and_not_from_exception():
    assert issubclass(Stopped, BaseException) and not issubclass(Stopped, Exception)


def test_the_finder_of_a_clause_that_catches_a_stop_sees_each_form():
    text = ("try:\n    pass\nexcept Stopped:\n    pass\nexcept (ValueError, stop.Stopped):\n    pass\n"
            "except Exception:\n    pass\nexcept BaseException:\n    pass\nexcept:\n    pass\n")
    assert [catches_a_stop(clause) for _, clause in handlers(ast.parse(text))] == [True, True, False, True, True]


def test_only_the_loop_catches_a_stop():
    found = [(path, where) for path, tree in sources() for where, clause in handlers(tree) if catches_a_stop(clause)]
    assert found == [("src/qdevices/runner/loop.py", "Loop._orders")]


def test_the_finder_of_blind_spots_sees_each_form():
    text = ("import contextlib\nfrom contextlib import suppress as quiet\nfrom .stop import Stopped as Halt\n"
            "BROAD = (ValueError, Exception)\nHALT: type = stop.Stopped\n\n\ndef f():\n"
            "    with contextlib.suppress(Exception):\n        pass\n    with suppress(OSError, BaseException):\n"
            "        pass\n    with contextlib.suppress(OSError):\n        pass\n    if (e := Stopped):\n"
            "        pass\n    x = ValueError\n    y: Final = frozenset({Exception})\n"
            "    z = getattr(builtins, \"BaseException\", None)\n")
    assert blind_spots(ast.parse(text)) == [2, 3, 4, 5, 9, 11, 15, 18, 19]


def test_no_broad_name_or_stop_is_suppressed_or_named_again_where_the_clause_finders_cannot_see_it():
    assert [(path, line) for path, tree in sources() for line in blind_spots(tree)] == []


def test_each_kind_of_stop_equals_its_text_and_has_the_exit_code_of_its_row():
    assert [(kind.name, kind, str(kind), kind.value, kind.code) for kind in StopKind] == [
        (name, text, text, text, code) for name, text, code in STOP_KINDS]


def test_every_event_of_a_record_golden_is_listed_in_record_py_and_none_is_expired():
    goldens = sorted((ROOT / "tests" / "golden").glob("record_*.txt"))
    if not goldens:
        pytest.skip("no record golden yet: tests/golden/record_*.txt are written with --golden=write")
    names = listed_events()
    found = [(path.name, event) for path in goldens for event in events_of(path)]
    assert found
    assert [(name, event) for name, event in found if event not in names or event == "expired"] == []


def test_the_finders_of_imports_names_and_unpicklers_see_each_form():
    text = ("import pickle as p\nfrom pickle import loads\nfrom ..sites import SITES, vlq\nfrom . import call\n"
            "NAMES = tuple(SITES)\n\n\nclass A:\n    x = configs.SITES\n\n\n@pick(SITES)\ndef f(a=SITES) -> None:\n"
            "    return SITES, p.Unpickler, lambda: SITES\n")
    tree = ast.parse(text)
    assert [(line, name) for line, name in imports("src/qdevices/runner/x.py", tree) if line > 2] == [
        (3, "qdevices.sites"), (3, "qdevices.sites.vlq"), (4, "qdevices.runner"), (4, "qdevices.runner.call")]
    assert reads_at_import(tree, "SITES") == [5, 9, 12, 13]
    assert unpickles(tree) == [2, 14]


def test_outside_sites_an_import_of_the_sites_is_of_the_registry_base_protocol_or_facts():
    found = [(path, line, name) for path, tree in sources() if not path.startswith(SITES_DIR)
             for line, name in imports(path, tree) if f"{name}.".startswith("qdevices.sites.")]
    assert [row for row in found if row[2] not in OPEN_TO_ALL] == []


def test_no_module_under_sites_imports_the_app_above_it():
    found = [(path, line, name) for path, tree in sources() if path.startswith(SITES_DIR)
             for line, name in imports(path, tree) if f"{name}.".startswith("qdevices.")]
    assert [row for row in found if not f"{row[2]}.".startswith(BELOW_SITES)] == []


def test_the_facts_import_the_standard_library_only_and_only_the_restricted_reader_unpickles():
    trees, facts = dict(sources()), f"{SITES_DIR}facts.py"
    assert [name for _, name in imports(facts, trees[facts]) if name.split(".")[0] not in sys.stdlib_module_names] == []
    assert [path for path, tree in trees.items() if unpickles(tree)] == [f"{SITES_DIR}pickle_reader.py"]


def test_outside_sites_the_registry_is_read_only_when_a_function_runs():
    assert [(path, line) for path, tree in sources() if not path.startswith(SITES_DIR)
            for line in reads_at_import(tree, "SITES")] == []


def test_only_the_registry_names_its_dict_so_a_machine_is_registered_there_alone():
    named = [p for p in sorted((ROOT / "src").rglob("*.py")) if "_REGISTRY" in p.read_text(encoding="utf-8")]
    assert named == [ROOT / SITES_DIR / "__init__.py"]
