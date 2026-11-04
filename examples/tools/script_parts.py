"""What the two writers of the scripts share."""

import builtins
import keyword
from math import gcd, pi
from textwrap import indent
from typing import Final

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


def angle_text(value: float) -> str:
    """An angle as code: a fraction of pi where it is one to the last bit, else the decimal of the same float."""
    for down in (1, 2, 3, 4, 6, 8, 12, 16, 32, 64):
        for up in (k for k in range(1, 4 * down) if gcd(k, down) == 1):
            if abs(value) == up * pi / down:
                sign, times, over = "-" if value < 0 else "", "" if up == 1 else f"{up} * ", f" / {down}"
                return f"{sign}{times}np.pi{over if down > 1 else ''}"
    return repr(float(value))


def main_block(loop: str, qasm: str = "") -> str:
    """The main block of a script: the loop of the shares, under a --qasm branch where there is one."""
    head = '\n\nif __name__ == "__main__":\n'
    if not qasm:
        return head + indent(loop, "    ")
    branch = '    if sys.argv[1:2] == ["--qasm"]:\n' + indent(qasm, "        ")
    return head + branch + "    else:\n" + indent(loop, "        ")


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
