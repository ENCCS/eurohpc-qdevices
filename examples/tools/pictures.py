"""Pictures of an example: its circuit, drawn by qutip-qip, and the share of each key from each source, as bars.

For writers, tests and notebooks only: it needs matplotlib, and qutip-qip for a circuit. emulate.sh never imports it.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from unittest import mock

import matplotlib.pyplot as plt
from circuit import Circuit, circuit_of
from emulate import QRISP_FILE, QUTIP_FILE, came_back, jobs_of, stored
from palette import BLUE, GREY, GRID, INK, ORANGE, TEAL

ONE_QUBIT, TWO_QUBIT = BLUE, ORANGE
SOURCES = (("a perfect machine, our emulator", GREY), ("QuTiP, stored", BLUE), ("Qrisp's emulator, stored", TEAL),
           ("the machine, one run, \u00b1 one shot error", ORANGE))
NAMES = {"h": "H", "x": "X", "y": "Y", "z": "Z", "s": "S", "sdg": "Sdg", "t": "T", "tdg": "Tdg", "rx": "RX",
         "ry": "RY", "rz": "RZ", "u3": "U3", "r": "R", "cx": "CX", "cy": "CY", "cz": "CZ", "crz": "CRZ",
         "move": "MOVE", "rxx": "RXX"}
CONTROLLED = ("cx", "cy", "cz", "crz")                   # the first qubit controls the second
DPI = 100
MANY_BITS = 3                                            # above this, one classical wire takes every bit


def _gate(name: str, qubits: tuple, args: tuple):
    from qutip_qip.operations import Gate

    style = {"color": TWO_QUBIT if len(qubits) == 2 else ONE_QUBIT, "fontcolor": "white", "showarg": len(args) == 1}
    controlled = name in CONTROLLED
    return Gate(NAMES[name], targets=[qubits[-1]] if controlled else list(qubits),
                controls=[qubits[0]] if controlled else None, arg_value=args[0] if len(args) == 1 else None,
                style=style)


def _qutip_circuit(circuit: Circuit, most: int, one_wire: bool) -> tuple:
    """The qutip-qip circuit of the first `most` gates and the measurements, and the label of each wire."""
    from qutip_qip.circuit import QubitCircuit

    qubits, one_wire = circuit.qubits, one_wire or len(circuit.bits) > MANY_BITS
    wire, cbits = {q: n for n, q in enumerate(qubits)}, 1 if one_wire else len(circuit.bits)
    qc = QubitCircuit(len(qubits), num_cbits=cbits)
    for name, on, args in circuit.ops[:most]:
        qc.add_gate(_gate(name, tuple(wire[q] for q in on), args))
    for place, qubit in enumerate(circuit.bits):          # the first character of a key is the highest classical bit
        qc.add_measurement("M", targets=[wire[qubit]], classical_store=0 if one_wire else cbits - 1 - place)
    labels = ["$c$"] if one_wire else [f"$c_{{{n}}}$" for n in range(cbits)]
    return qc, [*labels, *(f"$q_{{{q}}}$" for q in qubits)]


def _title(circuit: Circuit, most: int, title: str) -> str:
    gates, qubits = len(circuit.ops), circuit.qubits
    whole = f"{gates} gate" if gates == 1 else f"{gates} gates"
    cut = f"the first {most} of {gates} gates, then the measurements" if gates > most else whole
    cut += "; idle qubits not drawn" if qubits and len(qubits) <= qubits[-1] else ""
    return f"{title}: {cut}" if title else cut


def circuit_figure(circuit: Circuit, most: int = 30, title: str = "", one_wire: bool = False):
    """The gates of a circuit, as sent, and its measured qubits; a long one cut to its first `most` gates.

    One classical wire takes every bit above MANY_BITS bits, or if `one_wire`: for the broker's list, which has none.
    """
    from qutip_qip.circuit.mat_renderer import MatRenderer

    qc, labels = _qutip_circuit(circuit, most, one_wire)
    fig, ax = plt.subplots(dpi=DPI)
    drawing = MatRenderer(qc, ax=ax, dpi=DPI, wire_color=INK, wire_label=labels, title=_title(circuit, most, title))
    with mock.patch.object(plt, "show"):                  # qutip-qip shows the figure itself; we return it
        drawing.canvas_plot()
    (left, right), (low, high) = ax.get_xlim(), ax.get_ylim()
    fig.set_size_inches(right - left, high - low + 0.4)  # one unit is one inch, as qutip-qip measures its text
    return fig


@dataclass(frozen=True)
class Outcome:
    """One job: the share of each key on a perfect machine, on QuTiP and Qrisp if stored, and the counts if it ran."""

    name: str
    perfect: dict
    qutip: dict | None = None
    qrisp: dict | None = None
    counts: dict | None = None

    def sources(self) -> list:
        """(label, colour, shares, shots) of each source this job has; shots is 0 for an emulator."""
        held = (self.perfect, self.qutip, self.qrisp, self.counts)
        out = []
        for (label, colour), shares in zip(SOURCES, held, strict=True):
            if shares:
                shots = sum(shares.values()) if shares is self.counts else 0
                out.append((label, colour, {k: v / shots for k, v in shares.items()} if shots else shares, shots))
        return out

    @property
    def top(self) -> str:
        """The key a perfect machine gives most."""
        return max(sorted(self.perfect), key=self.perfect.get)


def folder_outcomes(folder: Path) -> list:
    """The outcome of each job of a folder: its circuit, its stored files, and its results.json if it ran."""
    back, qutip, qrisp = came_back(folder), stored(folder, QUTIP_FILE), stored(folder, QRISP_FILE)
    return [Outcome(job["name"], circuit_of(folder / job["file"]).shares(), qutip.get(job["name"]),
                    qrisp.get(job["name"]), back.get(job["name"])) for job in jobs_of(folder)]


def _keys(outcome: Outcome) -> list:
    """The keys of a job, by the largest share any source gives them."""
    largest = {}
    for _, _, shares, _ in outcome.sources():
        for key, value in shares.items():
            largest[key] = max(largest.get(key, 0.0), value)
    return sorted(largest, key=lambda key: (-largest[key], key))


@dataclass(frozen=True)
class Group:
    """The bars above one label: the share of some keys of one job, or of every other key if `rest`."""

    label: str
    outcome: Outcome
    keys: tuple
    rest: bool = False

    def bar(self, source: str) -> tuple | None:
        """The share and the shots of one source, or None if this job does not have it."""
        for label, _, shares, shots in self.outcome.sources():
            if label == source:
                held = sum(shares.get(key, 0.0) for key in self.keys)
                return (max(1 - held, 0.0) if self.rest else held), shots
        return None


def _groups(outcomes: list, most: int) -> list:
    """The top keys of one job, the rest as other; or the top key of each of several jobs."""
    if len(outcomes) > 1:
        return [Group(f"{o.name}\n{o.top}", o, (o.top,)) for o in outcomes]
    keys = _keys(outcomes[0])
    groups = [Group(key, outcomes[0], (key,)) for key in keys[:most]]
    return [*groups, Group("other", outcomes[0], tuple(keys[:most]), rest=True)] if len(keys) > most else groups


def _axes(labels: list):
    """Axes for bars over these labels: wider for many labels, and taller, with the keys upright, for long keys."""
    longest = max(len(line) for label in labels for line in label.split("\n"))
    upright = {"rotation": 90, "fontfamily": "monospace", "fontsize": 8} if longest > 8 else {}
    size = (max(6.4, 0.7 * len(labels) + 1.0), 3.4 + (0.07 * longest if upright else 0.0))
    fig, ax = plt.subplots(figsize=size, dpi=120)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=INK)
    ax.set_xticks(range(len(labels)), labels, color=INK, **upright)
    return fig, ax


def outcomes_figure(outcomes: list, most: int = 6, title: str = ""):
    """Bars of the share each source gives: of each top key for one job, or of the top key of each of several jobs."""
    groups = _groups(outcomes, most)
    present = [(label, colour) for label, colour in SOURCES if any(g.bar(label) for g in groups)]
    width = 0.8 / len(present)
    fig, ax = _axes([g.label for g in groups])
    for n, (label, colour) in enumerate(present):
        bars = [(place, g.bar(label)) for place, g in enumerate(groups) if g.bar(label)]
        errors = [sqrt(v * (1 - v) / shots) if shots else 0.0 for _, (v, shots) in bars]
        ax.bar([place - 0.4 + width * (n + 0.5) for place, _ in bars], [v for _, (v, _) in bars], width=width,
               color=colour, edgecolor="white", linewidth=1.5, label=label, yerr=errors if any(errors) else None,
               error_kw={"ecolor": INK, "elinewidth": 1, "capsize": 0})
    ax.set_ylabel("share of the shots", color=INK)
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=2, labelcolor=INK, fontsize=9)
    if title:
        ax.set_title(title, color=INK, fontsize=10, pad=44)
    fig.tight_layout()
    return fig
