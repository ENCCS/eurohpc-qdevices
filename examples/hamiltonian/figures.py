"""The charts of the tutorial: exact curves with measured points, the read share against the steps, and hydrogen."""

from math import sqrt
from typing import Final

import matplotlib.pyplot as plt
import numpy as np
from chain import T, closed_form
from hydrogen import Curve
from molecule import Molecule
from palette import BLUE, GREY, GRID, INK, ORANGE, TEAL
from reading import Reading
from reference import LARGE, NAMES, Reference

COLOURS: Final = {"001": BLUE, "010": TEAL, "100": ORANGE}
SITES: Final = {"001": "q[0]", "010": "q[1]", "100": "q[2]"}
FLOOR: Final = 1e-5                 # the bottom of the log axis of the hydrogen chart
REACH: Final = (0.35, 4.0)          # the bond lengths of the curve of hydrogen, in angstrom


def _axes(width: float = 7.2, height: float = 3.6):
    fig, ax = plt.subplots(figsize=(width, height), dpi=120)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=INK)
    return fig, ax


def _error(share: float, shots: int) -> float:
    return sqrt(share * (1 - share) / shots)


def _exact_curves(ax) -> None:
    times = np.linspace(0, 2 * T, 400)
    for key, colour in COLOURS.items():
        ax.plot(times, [closed_form(t)[key] for t in times], color=colour, linewidth=2, label=f"{key}: on {SITES[key]}")
    for x, y, key in ((0.0, 1.03, "001"), (T / 2, 0.53, "010"), (T, 1.03, "100"), (2 * T, 1.03, "001")):
        ax.text(x, y, key, color=INK, ha="center", fontsize=10)


def _point(ax, t: float, read: Reading, key: str) -> None:
    share = read.raw.get(key, 0.0)
    ax.errorbar(t, share, yerr=_error(share, read.shots), fmt="o", color=COLOURS[key], markersize=7,
                markeredgecolor="white", markeredgewidth=1.2, capsize=0, elinewidth=1.2)


def curves(points: dict[float, list[Reading]] | None = None):
    """The exact share of each key against the time; with `points`, the shares read at each time, with shot errors."""
    fig, ax = _axes()
    _exact_curves(ax)
    for t, readings in (points or {}).items():
        for read in readings:
            for key in COLOURS:
                _point(ax, t, read, key)
    ax.set_xticks([0, T / 2, T, 3 * T / 2, 2 * T], ["0", "T/2", "T", "3T/2", "2T"])
    ax.set_xlabel("time", color=INK)
    ax.set_ylabel("share of the shots", color=INK)
    ax.set_ylim(-0.03, 1.12)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=3)
    fig.tight_layout()
    return fig


def _read_marks(ax, place: int, read: Reading, labels: tuple[str | None, str | None]) -> None:
    raw, post = read.raw.get("100", 0.0), read.post.get("100", 0.0)
    ax.errorbar(place, raw, yerr=_error(raw, read.shots), fmt="o", color=COLOURS["100"], markersize=8,
                markeredgecolor="white", markeredgewidth=1.2, elinewidth=1.2, label=labels[0])
    ax.plot(place, post, "o", markerfacecolor="white", markeredgecolor=COLOURS["100"], markeredgewidth=1.6,
            markersize=8, label=labels[1])


def sweep(rows: list[tuple[int, int, float, list[Reading]]], emulated: list[float] | None = None):
    """The share of 100 at T against the steps: each row is N, two-qubit gates, the perfect share, the readings."""
    fig, ax = _axes()
    places = range(len(rows))
    if emulated:
        ax.plot(places, emulated, color=COLOURS["001"], linewidth=2, marker="s", markersize=6,
                label="emulated, with this noise")
    ax.plot(places, [row[2] for row in rows], color="#999999", linewidth=2, linestyle="--", marker="o", markersize=6,
            label="a perfect machine: the error of the steps alone")
    named = ("read, every shot", "read, with the conservation check")
    for i, row in enumerate(rows):
        for k, read in enumerate(row[3]):
            _read_marks(ax, i, read, named if i == 0 and k == 0 else (None, None))
    ax.set_xticks(list(places), [f"N = {n}\n{gates} two-qubit gates\nin the text" for n, gates, _, _ in rows])
    ax.set_ylabel("share of the key 100", color=INK)
    ax.set_ylim(0, 1.08)
    ax.legend(frameon=False, loc="lower left", bbox_to_anchor=(0.1, 0.0))
    fig.tight_layout()
    return fig


def phases(energy_of: dict[float, float]):
    """The share of each energy that phase estimation reads, on a log scale: the grid, and the weight of each level."""
    fig, ax = _axes(height=3.0)
    energies, shares = zip(*sorted(energy_of.items()), strict=True)
    ax.bar(energies, [max(share - FLOOR, 0.0) for share in shares], width=0.07, bottom=FLOOR, color=COLOURS["001"])
    ax.set_yscale("log")
    ax.set_ylim(FLOOR, 2)
    ax.set_xlabel("energy read, in hartree", color=INK)
    ax.set_ylabel("share of the shots", color=INK)
    fig.tight_layout()
    return fig


def _small_basis(ax, lengths: np.ndarray) -> None:
    molecules = [Molecule(float(r)) for r in lengths]
    ax.plot(lengths, [m.hartree_fock for m in molecules], color=GREY, linewidth=2, linestyle="--",
            label="restricted Hartree-Fock, STO-3G")
    ax.plot(lengths, [m.exact for m in molecules], color=COLOURS["001"], linewidth=2, label="exact in STO-3G (FCI)")


def _large_basis(ax) -> None:
    reference = Reference.load()
    ax.plot(reference.lengths, [reference.fci(LARGE, r) for r in reference.lengths], color=COLOURS["010"], linewidth=2,
            label=f"FCI, {NAMES[LARGE]}")
    lengths, energies = zip(*reference.points(*REACH), strict=True)
    ax.plot(lengths, energies, "o", markerfacecolor="white", markeredgecolor=COLOURS["010"], markeredgewidth=1.4,
            markersize=6, label="published, complete basis")


def dissociation(run: Curve):
    """Total energy against bond length: the methods, and the emulated readings, with half a grid step either way."""
    fig, ax = _axes(height=4.4)
    _small_basis(ax, np.linspace(*REACH, 200))
    _large_basis(ax)
    ax.errorbar([p.length for p in run.points], [p.energy for p in run.points], yerr=run.grid / 2, fmt="s",
                color=COLOURS["100"], markersize=4, markeredgewidth=0, elinewidth=1.2, capsize=3,
                label=f"phase estimation in STO-3G, {run.bits} bits, emulated")
    ax.set_xlabel("bond length, in angstrom", color=INK)
    ax.set_ylabel("total energy, in hartree", color=INK)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=2)
    fig.tight_layout()
    return fig


def overlaps():
    """The squared overlap of the restricted Hartree-Fock state with the ground state in STO-3G, against bond length."""
    fig, ax = _axes(height=2.6)
    lengths = np.linspace(*REACH, 200)
    ax.plot(lengths, [Molecule(float(r)).overlap for r in lengths], color=COLOURS["001"], linewidth=2)
    ax.set_xlabel("bond length, in angstrom", color=INK)
    ax.set_ylabel("squared overlap", color=INK)
    ax.set_ylim(0, 1.05)
    fig.tight_layout()
    return fig
