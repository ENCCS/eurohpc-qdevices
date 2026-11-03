"""Write qutip_emulated.json by QuTiP with no noise, in each example folder or in those named: `qutip-emulated`."""

# It makes no network call and sends nothing. Each job runs on the qubits it uses, so the 25-qubit job takes the most.
import json
import sys
from importlib.metadata import version
from pathlib import Path
from typing import Final

from emulate import QUTIP_FILE
from overview import write_stored
from qutip_emulator import folder_shares

EXAMPLES: Final = Path(__file__).resolve().parent.parent


def _block(rows: dict) -> str:
    lines = ",\n".join(f"    {json.dumps(name)}: {json.dumps(value)}" for name, value in rows.items())
    return f"{{\n{lines}\n  }}" if rows else "{}"


def stored_text(folder: Path) -> str:
    """The file of one folder: the versions of QuTiP and qutip-qip, one line for each job, and why any did not run."""
    shares, not_run = folder_shares(folder)
    return (f'{{\n  "qutip": {json.dumps(version("qutip"))},\n  "qutip_qip": {json.dumps(version("qutip-qip"))},\n'
            f'  "jobs": {_block(shares)},\n  "not_run": {_block(not_run)}\n}}\n')


if __name__ == "__main__":
    write_stored(EXAMPLES, QUTIP_FILE, stored_text, [Path(a).resolve() for a in sys.argv[1:]])
