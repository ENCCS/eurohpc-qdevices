"""The counts of the newest record of an example, top keys first: `./run.sh --counts` in its folder."""

import sys
from pathlib import Path

from emulate import fractions, top

from qdevices import manifest as manifests
from qdevices.finder import AppRecords
from qdevices.ledger import Ledger
from qdevices.paths import Places
from qdevices.record import RecordError, RecordLines
from qdevices.sites import SITES


def lines(events: list[dict]) -> list[str]:
    """One line for each job of a record: the share of its top keys, or the state of the order."""
    ledger, out = Ledger(events), []
    for job in ledger.start["jobs"]:
        order = ledger.orders.get(job["order"])
        result = order.result if order is not None else None
        if result and result.get("counts"):
            out.append(f"{job['name']:<14} {sum(result['counts'].values())} shots  {top(fractions(result['counts']))}")
        else:
            out.append(f"{job['name']:<14} {(order.final or order.status) if order is not None else 'not sent'}")
    return out


def main(argv: list[str]) -> int:
    """Print the counts for the manifest given; 1 when no record of it can be read."""
    try:
        man = manifests.load(Path(argv[0]), SITES)
    except manifests.ManifestError as exc:
        print(f"This example cannot be read: {exc}")
        return 1
    folder = Path(Places.default().records) / man["site"] / man["run"]
    record = AppRecords(folder).newest()
    if record is None:
        print(f"No record in {folder}: this example has not been sent from this computer.")
        return 1
    try:
        print(f"Record: {record}\n" + "\n".join(lines(RecordLines.read(record).events)))
    except RecordError as exc:
        print(exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
