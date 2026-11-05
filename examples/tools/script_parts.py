"""What the two writers of the scripts share."""

import builtins
import keyword
import sys
from math import gcd, pi
from pathlib import Path
from textwrap import indent
from typing import Final

from script_qasm import qasm_branch, usage

BUILTINS: Final = frozenset(dir(builtins))       # a job function of one of these names would hide it from the script
KEYS: Final = {"broker": "a key reads qubit 0 first, as the broker gives it, and the angles of its list, in units of "
                         "pi, are in radians here",
               "text": "the first character of a key is the highest classical bit, as on the site"}
TOP: Final = '''

def top(shares, most=6):
    """The keys with the largest shares, as one line, as emulate.sh prints them."""
    rows = sorted(shares.items(), key=lambda kv: (-round(kv[1], 9), kv[0]))[:most]
    more = f"  and {len(shares) - most} more" if len(shares) > most else ""
    return "  ".join(f"{key}: {value:.3f}" for key, value in rows) + more
'''
# python FILE sets __file__, sys.orig_argv (Python 3.10 or later) ends with sys.argv, and sys.argv[0] is that file.
# Under python -m, %run and runpy, as Choose one runs a script, sys.argv[0] is the script, while the command line
# runs a module or the host. A pasted cell may have no __file__, or one left by %run -i, and sys.argv[0] is the host.
ARGS: Final = ("# The script reads its arguments when sys.orig_argv (Python 3.10 or later) ends with sys.argv and "
               "sys.argv[0] is\n# the file in __file__, as with python FILE; else (python -m, a Jupyter kernel) only "
               "when the first is --qasm.\n"
               'program = ("__file__" in globals() and getattr(sys, "orig_argv", [])[-len(sys.argv):] == sys.argv\n'
               "           and sys.argv and os.path.realpath(sys.argv[0]) == os.path.realpath(__file__))\n"
               'args = sys.argv[1:] if program or sys.argv[1:2] == ["--qasm"] else []\n')
MAIN_IMPORT: Final = "import os\nimport sys\n"      # what the main block needs, in the imports of each script


def angle_text(value: float) -> str:
    """An angle as code: a fraction of pi where it is one to the last bit, else the decimal of the same float."""
    for down in (1, 2, 3, 4, 6, 8, 12, 16, 32, 64):
        for up in (k for k in range(1, 4 * down) if gcd(k, down) == 1):
            if abs(value) == up * pi / down:
                sign, times, over = "-" if value < 0 else "", "" if up == 1 else f"{up} * ", f" / {down}"
                return f"{sign}{times}np.pi{over if down > 1 else ''}"
    return repr(float(value))


def main_block(folder: Path, script: str, loop: str, writes: str) -> str:
    """The main block of a script: the loop of the shares with no argument, the --qasm branch, else a usage line.

    In a folder of Euro-Q-Exa the --qasm branch is `writes`, which prints OpenQASM 2; in another it is a stop that says
    what that site takes.
    """
    return ('\n\nif __name__ == "__main__":\n' + indent(ARGS, "    ") + "    if not args:\n" + indent(loop, "        ")
            + '    elif args[0] == "--qasm":\n' + indent(qasm_branch(folder, writes), "        ")
            + f'    else:\n        sys.exit("usage: {usage(folder, script)}")\n')


def main_imports(lines: str = "") -> str:
    """The lines `import NAME` of MAIN_IMPORT and of `lines` in one block, in the order of ruff's isort rule."""
    return "".join(sorted({*MAIN_IMPORT.splitlines(keepends=True), *lines.splitlines(keepends=True)}))


def commented(items, why: dict, explained: set, line) -> list:
    """Each item as one indented line; before the first of each gate that `why` explains, a comment line."""
    lines = []
    for item in items:
        if item.ours in why and item.ours not in explained:
            explained.add(item.ours)
            lines.append(f"    # {item.ours}: {why[item.ours]}")
        lines.append(f"    {line(item)}")
    return lines


def keys_of(jobs: list) -> str:
    """What a key of the folder's jobs reads, as the docstring of each script says it."""
    return KEYS["broker" if all(job["file"].endswith(".json") for job in jobs) else "text"]


def example_path(folder: Path, root: Path) -> str:
    """The path of a folder below `root`, which its scripts name; a stop of one line for a folder elsewhere."""
    if not folder.is_relative_to(root):
        sys.exit(f"{folder}: emulate_qutip.py and emulate_qrisp.py are written in the example folders below "
                 "examples/ only")
    return folder.relative_to(root).as_posix()


def function_of(name: str, taken: set, defined: dict) -> str:
    """The function of a job: its name in lower case, kept in `defined` under the name of the job.

    It must be a free Python name: no keyword, none of `taken`, no builtin, no function of a job before it, and no
    two underscores first, as a script binds __file__ and __builtins__ itself.
    """
    function, used = name.lower(), taken | BUILTINS | set(defined.values())
    if (not function.isidentifier() or keyword.iskeyword(function) or function.startswith("__")
            or function in used):
        raise ValueError(f"a job name that is not a free Python name: {name}")
    defined[name] = function
    return function
