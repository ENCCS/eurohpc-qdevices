"""All the examples in one table and one chart, for the page all_examples.ipynb."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from circuit import circuit_of
from emulate import came_back, fractions, qrisp_stored, qutip_stored
from palette import BLUE, GRID, INK

MARKED = ("STEPS8", "SHOR13", "ISING", "ISING2", "QRISP", "GROVER3", "HELLO", "QITE1", "QUBO")
HEAD = (f"{'folder':<28} {'job':<19} {'site':<9} {'q':>2} {'2q':>4} {'key':<26} {'perfect':>7} {'vs Qrisp':>8} "
        f"{'vs QuTiP':>8} {'read':>6}")


@dataclass(frozen=True)
class Row:
    """One job: where, its size, a perfect machine's best key and share, the gaps to Qrisp and QuTiP, the read."""

    folder: str
    job: str
    site: str
    qubits: int
    gates: int
    key: str
    perfect: float
    apart: float | None
    read: float | None
    qutip_apart: float | None = None

    def __str__(self) -> str:
        """The line of the table, with QuTiP's gap in powers of ten; the last cell is empty for a job not sent yet."""
        read = f"{self.read:>6.3f}" if self.read is not None else ""
        apart = f"{self.apart:>8.6f}" if self.apart is not None else " " * 8
        qutip = f"{self.qutip_apart:>8.1e}" if self.qutip_apart is not None else " " * 8
        return (f"{self.folder:<28} {self.job:<19} {self.site:<9} {self.qubits:>2} {self.gates:>4} {self.key:<26} "
                f"{self.perfect:>7.3f} {apart} {qutip} {read}")


def largest_apart(ours: dict, theirs: dict) -> float:
    """The largest difference between two sets of shares, in any key."""
    return max(abs(ours.get(key, 0.0) - theirs.get(key, 0.0)) for key in ours.keys() | theirs.keys())


def _rows_of(folder: Path) -> list:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    back, qrisp, qutip = came_back(folder), qrisp_stored(folder), qutip_stored(folder)
    rows = []
    for job in manifest["jobs"]:
        circuit = circuit_of(folder / job["file"])
        shares = circuit.shares()
        best = max(sorted(shares), key=shares.get)
        read = fractions(back[job["name"]]).get(best, 0.0) if job["name"] in back else None
        apart = largest_apart(shares, qrisp[job["name"]]) if job["name"] in qrisp else None
        qutip_apart = largest_apart(shares, qutip[job["name"]]) if job["name"] in qutip else None
        rows.append(Row(folder.as_posix(), job["name"], manifest["site"], len(circuit.bits), circuit.two_qubit, best,
                        shares[best], apart, read, qutip_apart))
    return rows


def example_folders(root: Path) -> tuple:
    """Every folder below `root` that holds a manifest."""
    return tuple(sorted(p.parent for p in root.rglob("manifest.json") if ".pixi" not in p.parts))


def write_stored(root: Path, name: str, text_of) -> None:
    """Write the file `name` in each example folder below `root`, as `text_of(folder)` gives it, and print where."""
    for folder in example_folders(root):
        (folder / name).write_bytes(text_of(folder).encode("utf-8"))
        print(folder.relative_to(root) / name)


@dataclass(frozen=True)
class Overview:
    """Each job of each example folder."""

    folders: tuple
    rows: tuple

    @classmethod
    def of(cls, root: Path) -> Overview:
        """The rows of every folder below `root` that holds a manifest."""
        folders = example_folders(root)
        return cls(folders, tuple(row for folder in folders for row in _rows_of(folder)))

    def table(self) -> str:
        """All the jobs, one line each."""
        return "\n".join([HEAD, *map(str, self.rows)])

    def chart(self):
        """The share read over the perfect share, against the two-qubit gates, for each job that has run."""
        import matplotlib.pyplot as plt

        points = [(row.gates, row.read / row.perfect, row.job) for row in self.rows if row.read is not None]
        fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=120)
        ax.grid(axis="y", color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        ax.scatter([p[0] for p in points], [p[1] for p in points], s=46, color=BLUE, edgecolor="white",
                   linewidth=1.2)
        for gates, value, job in (p for p in points if p[2] in MARKED):
            ax.annotate(job, (gates, value), textcoords="offset points", xytext=(6, 5), fontsize=8, color=INK)
        ax.set_xscale("symlog", linthresh=10)
        ax.set_xticks([0, 5, 10, 20, 50, 100], ["0", "5", "10", "20", "50", "100"])
        ax.set_xlabel("two-qubit gates in the text", color=INK)
        ax.set_ylabel("share read, over the perfect share", color=INK)
        ax.set_ylim(0, 1.08)
        fig.tight_layout()
        return fig
