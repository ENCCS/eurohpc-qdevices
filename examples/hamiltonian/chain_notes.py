"""What the READMEs of the two folders of the chain say."""

from typing import Final

from readme import Readme

ABOUT: Final = ("The jobs of the tutorial in `examples/hamiltonian/`: start there. One excitation crosses three qubits "
                "under `H = (1/2) sum (XX + YY)`, and arrives in full at `T = pi/sqrt 2`. The jobs are CONTROL (no "
                "evolution), MAIN and QRISP (the same evolution as two texts), REPEAT (the text of MAIN again, to see "
                "how far two jobs of one circuit differ), HALF (at T/2), BACK (at 2T, when it has returned), ZERO (the "
                "same gates with no excitation), STEPS1, STEPS4, STEPS8 (other numbers of Trotter steps) and ORDER1 "
                "(first order).")
STEPS: Final = ("Start: 001", "Rx(pi/2) on all", "MAIN: five bonds in turn, q0-q1, q1-q2, q0-q1, q1-q2, q0-q1",
                "Rx(-pi/2) on all", "Measure", "100, on arrival")
PERFECT: Final = ("`100` at 0.970 for MAIN, QRISP and REPEAT; `001` for CONTROL, and at 0.988 for BACK; `000` for "
                  "ZERO. A key reads q[2] q[1] q[0]. `manifest.json` holds the shares of each job.")
BACK: Final = ("`100` in 641 of 1000 for MAIN, 661 for REPEAT, 696 for QRISP; 381, 474 and 190 for 1, 4 and 8 "
               "steps. The tutorial reads them all.")
LIVE_ABOUT: Final = ("One job, for a talk: you run it on the quantum computer while people follow the tutorial in "
                     "`examples/hamiltonian/`, and anyone who wants to try it emulates it. It is the job MAIN of "
                     "`state_transfer/`, the same text: one excitation crosses three qubits in two Trotter steps. "
                     "After the send, from the top of the clone, `pixi run python examples/hamiltonian/compare.py "
                     "--live` prints the table and writes `live.json`, which the tutorial reads in place of the first "
                     "run. The app refuses a second send from this folder; `pixi run qdevices send manifest.json "
                     "--live --new-run --max-order 1` is a new job on your award.")
LIVE_PERFECT: Final = "`100` at 0.970, then `001` at 0.027. A key reads q[2] q[1] q[0]."
LIVE_BACK: Final = "The first run of this text, 1000 shots: `100`: 641, then `110`: 83."
MADE_BY: Final = ("Written by `examples/hamiltonian/write_chain.py`. To change a job, change it there and run the "
                  "script again.")
LIVE_PAGE: Final = Readme("euroqexa", "The job for a talk", LIVE_ABOUT, STEPS, LIVE_PERFECT, LIVE_BACK, ("MAIN.qasm",),
                          made_by=MADE_BY)


def page_of_all(jobs: int) -> Readme:
    """The README of the folder that holds all the jobs."""
    return Readme("euroqexa", "The jobs of the Hamiltonian tutorial", ABOUT, STEPS, PERFECT, BACK, ("*.qasm",),
                  jobs=jobs, made_by=MADE_BY)
