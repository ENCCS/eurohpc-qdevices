"""Write circuit.png and outcomes.png in each example folder: `pictures` in qrisp/pixi.toml.

It makes no network call and sends nothing. circuit.png is the circuit of one job, drawn by qutip-qip and cut to fit
a page: the job readme.DRAWN names for the folder, else its first job. outcomes.png is the share of each key from each
source of the folder, as bars.
"""

import argparse
from pathlib import Path
from typing import Final

import matplotlib.pyplot as plt
from circuit import Circuit, circuit_of
from emulate import jobs_of
from overview import example_folders
from pictures import circuit_figure, folder_outcomes, outcomes_figure
from readme import DRAWN

EXAMPLES: Final = Path(__file__).resolve().parent.parent
CIRCUIT: Final = "circuit.png"
OUTCOMES: Final = "outcomes.png"
SAVE: Final = {"metadata": {"Software": None}, "pil_kwargs": {"optimize": True}}   # no version and no date in a file
LONGEST: Final = 1200                                  # pixels: the longer side of a picture, at most
CUTS: Final = (30, 24, 20, 18, 16, 12)                 # the first gates kept of a long circuit, most first
WIDEST: Final = 12.0                                   # inches: fitted_figure cuts to this, where cutting helps


def fitted_figure(circuit: Circuit, title: str = "", widest: float = WIDEST, one_wire: bool = False):
    """The circuit with the most of CUTS gates that fit in `widest` inches; cut no further once that is no narrower."""
    fig = circuit_figure(circuit, CUTS[0], title, one_wire)
    for most in (m for m in CUTS[1:] if m < len(circuit.ops)):
        width = fig.get_size_inches()[0]
        if width <= widest:
            break
        narrower = circuit_figure(circuit, most, title, one_wire)
        if narrower.get_size_inches()[0] >= width:
            plt.close(narrower)
            break
        plt.close(fig)
        fig = narrower
    return fig


def name_of(folder: Path) -> str:
    """A folder's name under examples/, as a README gives it; its own name if it is elsewhere."""
    folder = folder.resolve()
    return folder.relative_to(EXAMPLES).as_posix() if folder.is_relative_to(EXAMPLES) else folder.name


def drawn_job(folder: Path) -> dict:
    """The job whose circuit a folder's circuit.png shows: the one DRAWN names, else the first."""
    jobs, name = jobs_of(folder), DRAWN.get(name_of(folder))
    return next((job for job in jobs if job["name"] == name), jobs[0])


def _save(fig, path: Path) -> int:
    fig.savefig(path, dpi=min(fig.dpi, LONGEST / max(fig.get_size_inches())), **SAVE)
    plt.close(fig)
    return path.stat().st_size


def figures(folder: Path) -> tuple:
    """The two pictures of a folder: the circuit of its drawn job, cut to fit, and the outcomes of all its jobs.

    The broker's list has no classical bits, so its picture has one classical wire.
    """
    job = drawn_job(folder)
    circuit = fitted_figure(circuit_of(folder / job["file"]), job["name"], one_wire=job["file"].endswith(".json"))
    return circuit, outcomes_figure(folder_outcomes(folder))


def write(folder: Path, out: Path) -> tuple:
    """Write the two pictures of one folder into `out`; their sizes in bytes."""
    circuit, outcomes = figures(folder)
    out.mkdir(parents=True, exist_ok=True)
    return _save(circuit, out / CIRCUIT), _save(outcomes, out / OUTCOMES)


def main(argv: list | None = None) -> int:
    """Write the pictures of each folder asked, or of all, and print the size of each."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="*", type=Path, help="example folders (default: every one)")
    parser.add_argument("--out", type=Path, help="write into OUT/<folder name> in place of the folder itself")
    args = parser.parse_args(argv)
    plt.switch_backend("Agg")
    total = 0
    for folder in [f.resolve() for f in args.folders] or example_folders(EXAMPLES):
        name = name_of(folder)
        sizes = write(folder, args.out / name if args.out else folder)
        total += sum(sizes)
        print(f"{name:<28} {CIRCUIT} {sizes[0] / 1024:5.1f} KB  {OUTCOMES} {sizes[1] / 1024:5.1f} KB")
    print(f"in all: {total / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
