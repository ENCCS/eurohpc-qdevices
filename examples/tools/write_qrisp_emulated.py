"""Write qrisp_emulated.json by Qrisp's emulator, in each example folder or in those named: `qrisp-emulated`."""

# It makes no network call and sends nothing.
import json
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Final

from emulate import QRISP_FILE
from overview import write_stored
from qrisp_emulator import folder_shares

EXAMPLES: Final = Path(__file__).resolve().parent.parent


def stored_text(folder: Path) -> str:
    """The file of one folder: the version of Qrisp, then one line for each job."""
    rows = ",\n".join(f"    {json.dumps(name)}: {json.dumps(said)}" for name, said in folder_shares(folder).items())
    return f'{{\n  "qrisp": {json.dumps(version("qrisp"))},\n  "jobs": {{\n{rows}\n  }}\n}}\n'


if __name__ == "__main__":
    write_stored(EXAMPLES, QRISP_FILE, stored_text, [Path(a).resolve() for a in sys.argv[1:]])
