"""Write this folder for Euro-Q-Exa: two texts by Qrisp, the manifest, the README and the scripts.

`two-spins` in examples/qrisp/pixi.toml. It makes no network call. It leaves results.json, the counts of the runs of
these two texts, as it is.
"""

import argparse
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "qrisp"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))
from by_qrisp import text
from example_folder import ExampleFolder
from readme import Readme

from qdevices.manifest import FORMAT
from qdevices.values import sha256_hex

HERE: Final = Path(__file__).resolve().parent
STEPS: Final = (5, 16)
NOTEBOOK: Final = ("https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=lab/tree/examples/hamiltonian/"
                   "two_spins/two_spins.ipynb")
ABOUT: Final = (
    f"[![Run on Binder](https://mybinder.org/badge_logo.svg)]({NOTEBOOK})\n\n"
    "The short start to Hamiltonian simulation: one short notebook, [`two_spins.ipynb`](two_spins.ipynb). Two spins of "
    "the Ising model in a transverse field, `H = -Z0 Z1 - 1.2 (X0 + X1)`, start in `00` and evolve to `t = 2 pi/2.6`, "
    "a time at which `01` and `10` are zero and `11` holds 0.874. The notebook solves the model exactly in QuTiP, "
    "writes the evolution as Trotter steps of CX, RZ and H, builds the same circuit in Qrisp, and reads two runs on "
    "Euro-Q-Exa: 5 steps, and 16.\n\n"
    "Why this model: it is a model of magnets such as LiHoF4 and CoNb2O6 in a field across their axis; quantum "
    "annealing changes its field over time; and one Trotter step, a short slice of the evolution written as gates, "
    "has the shape of one layer of QAOA, the quantum approximate optimisation algorithm. The notebook cites the "
    "papers. Two spins are solved exactly on any laptop, and the magnets, annealing and QAOA need many spins: the "
    "point here is to learn the steps that carry over. The [long tutorial](../tutorial.ipynb) goes on to three qubits "
    "and to the hydrogen molecule.")
FLOW: Final = ("Start: 00", "One Trotter step: CX, RZ, CX for ZZ; H, RZ, H for X on each spin", "5 steps, or 16",
               "Measure", "11 most often")
PERFECT: Final = ("`11` at 0.866 for STEPS5 and at 0.877 for STEPS16; with no Trotter error, 0.874. A key reads q[1] "
                  "q[0]. At this time the exact evolution puts nothing on `01` and `10`; 5 steps put 0.013 on each.")
BACK: Final = ("1000 shots each, from runs of these same texts; STEPS5 was sent as `qrisp/ising2`. STEPS5: `11`: 783, "
               "`00`: 95, `01`: 67, `10`: 55. STEPS16: `11`: 789, `00`: 113, `01`: 53, `10`: 45. The two read the same "
               "within the shot error, about 0.013, though STEPS16 has 32 CX in its text and STEPS5 has 10. On two "
               "qubits all the steps make one two-qubit block, which 2 CX can make, and the site's compile merged "
               "them: the circuit that ran, on the job page of the portal, has 2 CZ for each.")
MORE: Final = (("two_spins.ipynb", "the notebook: the model, the gates, Qrisp, the run, where the model is used, and "
               "what the run shows"),
               ("spins.py", "the model in QuTiP: its levels, the exact evolution, the Trotter steps, the chart"),
               ("by_qrisp.py", "the same in Qrisp: the function that writes the texts, and Qrisp's emulator"),
               ("trotter.py", "the steps as a text in Python alone, for other fields and steps"),
               ("machine.py", "the counts as shares with shot errors, and the simple model of the notebook"),
               ("write_two_spins.py", "writes this folder"))
MADE_BY: Final = ("This folder is written by `write_two_spins.py`; its texts come from `ising2` in "
                  "`examples/qrisp/programs.py`. To change a job, change it there and, from the top of the clone, run "
                  "`pixi run --manifest-path examples/qrisp/pixi.toml two-spins`: a text changed by hand no longer "
                  "matches its SHA-256.")
PAGE: Final = Readme("euroqexa", "Two spins in a field: the short start", ABOUT, FLOW, PERFECT, BACK,
                     tuple(f"STEPS{n}.qasm" for n in STEPS), jobs=len(STEPS), made_by=MADE_BY, more=MORE,
                     notebook=NOTEBOOK)


def job(order: int, steps: int, folder: Path, shots: int) -> dict:
    """Write the text of N steps and give its line of the manifest."""
    data = text(steps).encode("utf-8")
    (folder / f"STEPS{steps}.qasm").write_bytes(data)
    return {"order": order, "name": f"STEPS{steps}", "file": f"STEPS{steps}.qasm", "sha256": sha256_hex(data),
            "shots": shots, "steps": steps}


def main(argv: list[str] | None = None) -> int:
    """Write the folder and print the path of its manifest."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE)
    parser.add_argument("--machine", default="EQE1")
    parser.add_argument("--project", default="MY-PROJECT")
    parser.add_argument("--shots", type=int, default=1000)
    args = parser.parse_args(argv)
    folder = ExampleFolder(args.out, "hamiltonian/two_spins")
    folder.path.mkdir(parents=True, exist_ok=True)
    head = {"format": FORMAT, "site": "euroqexa", "machine": args.machine, "project": args.project,
            "made_with": "Qrisp, examples/hamiltonian/two_spins/write_two_spins.py",
            "ideal": "11 at 0.866 for STEPS5 and 0.877 for STEPS16; a key reads q[1] q[0]"}
    jobs = [job(order, steps, folder.path, args.shots) for order, steps in enumerate(STEPS, 1)]
    print(folder.write_manifest(head, jobs))
    folder.write_page(PAGE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
