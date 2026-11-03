"""Compare the counts in a record of the chain with the shares its manifest put in the record.

It makes no network call. It needs the app, and no Qrisp or QuTiP. A key reads q[2] q[1] q[0].
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from reading import Reading, distance

from qdevices.finder import AppRecords
from qdevices.ledger import Ledger, Outcome
from qdevices.paths import Places
from qdevices.record import RecordError, RecordLines

LIVE: Final = Path(__file__).resolve().parent / "live.json"
HEAD: Final = (f"{'order':>5} {'name':<10} {'2q':>3} {'shots':>6} {'key':>4} {'exact':>6} {'text':>6} {'raw':>6} "
               f"{'kept':>6} {'post':>6} {'raw TVD':>8}")


@dataclass(frozen=True, slots=True)
class Compared:
    """A record of the chain: what each job gave, against its exact answer and against its own text."""

    ledger: Ledger

    @classmethod
    def read(cls, record: Path) -> "Compared":
        """The record in a file."""
        return cls(Ledger(RecordLines.read(record).events))

    def row(self, job: dict) -> str:
        """The line of one job: its state, or its shares against the exact answer and against its own text."""
        order, key, text = self.ledger.orders.get(job["order"]), job["key"], job["text_shares"]
        head = (f"{job['order']:>5} {job['name']:<10} {job['two_qubit']:>3} {job['shots']:>6} {key:>4} "
                f"{job['exact_shares'].get(key, 0.0):>6.3f} {text.get(key, 0.0):>6.3f}")
        if order is None or order.final != Outcome.RESULT:
            return f"{head}  {(order.final or order.status) if order else 'not sent'}"
        counts = order.result["counts"]
        if any(len(k) != len(key) for k in counts):
            return f"{head}  a key of another width: read the record"
        read = Reading(counts, job["excitations"])
        return (f"{head} {read.raw.get(key, 0.0):>6.3f} {read.kept:>6.3f} {read.post.get(key, 0.0):>6.3f} "
                f"{distance(read.raw, text):>8.3f}")

    def table(self) -> list[str]:
        """The table of the record: one line for each job of its start line."""
        return [HEAD, *(self.row(job) for job in self.ledger.start["jobs"])]

    def counts(self) -> dict[str, dict[str, int]]:
        """The counts of each job with a result, by its name: no id, no time and no project, so it can be shared."""
        done = ((job["name"], self.ledger.orders.get(job["order"])) for job in self.ledger.start["jobs"])
        return {name: order.result["counts"] for name, order in done
                if order is not None and order.final == Outcome.RESULT}


def newest_live() -> Path | None:
    """The newest record of the job for a talk: the folder `live`, here or in your own copy."""
    return AppRecords(Path(Places.default().records) / "euroqexa" / "live").newest()


def arguments(argv: list[str] | None) -> argparse.Namespace:
    """The command line: a record, or --live."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("record", type=Path, nargs="?")
    parser.add_argument("--export", type=Path, help="write the counts alone to this JSON file, to share them")
    parser.add_argument("--live", action="store_true", help="the newest record of live/: print its table, and write "
                        "live.json beside this script, which the tutorial reads")
    args = parser.parse_args(argv)
    if (args.record is not None) == args.live:
        parser.error("give a record, or --live")
    return args


def main(argv: list[str] | None = None) -> int:
    """Print the table of a record, or write its counts with --export, or both with --live; 1 if it cannot be read."""
    args = arguments(argv)
    record = newest_live() if args.live else args.record
    if record is None:
        print("No record of live/ on this computer: run ./submit.sh in that folder first.")
        return 1
    try:
        compared = Compared.read(record)
    except RecordError as exc:
        print(exc)
        return 1
    export = LIVE if args.live else args.export
    if export:
        export.write_text(json.dumps(compared.counts(), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.live or not export:
        print("\n".join(compared.table()))
    if args.live:
        print(f"Wrote {LIVE}: run the tutorial again and it reads these counts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
