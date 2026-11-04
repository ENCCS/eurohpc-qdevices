"""The examples written by hand: what each README says. `pixi run python examples/tools/folders.py` writes them."""

from pathlib import Path
from typing import Final

from example_folder import ExampleFolder
from readme import Readme

HERE: Final = Path(__file__).resolve().parent.parent
LRZ: Final = "From the LRZ training material of the pilot phase, `examples/04_reading_from_qasm.py`."


def by_hand(source: str = "") -> str:
    """How the texts were made, and how to change one: no code writes the texts of these folders."""
    return (f"{source + ' ' if source else ''}Each text here is written by hand: to change one, edit it and put its "
            "new SHA-256 in `manifest.json`, in each job that names it (`shasum -a 256 FILE` on a Mac, "
            "`sha256sum FILE` on Linux); the page of the site in the manual, linked below, says what the site takes.")


BELL: Final = ("Start: 00", "H on q[0]", "CX from q[0] to q[1]", "Measure", "00 and 11")
READMES: Final = {
    "euroqexa-one-qubit": Readme(
        "euroqexa", "One X gate on Euro-Q-Exa",
        "The smallest job: flip one qubit and read it. It tests the whole path, from your laptop to the machine and "
        "back, with no two-qubit gate, so a wrong answer can only come from the state preparation or the readout.",
        ("Start: 0", "X", "Measure", "1"),
        "`1` every time.", "", ("X.qasm",), made_by=by_hand()),
    "euroqexa-bell": Readme(
        "euroqexa", "A Bell pair on Euro-Q-Exa",
        "H on q[0], then CX: the state (|00> + |11>)/sqrt 2. Each qubit alone reads 0 or 1 at random, and the two "
        "always agree. It is the smallest test of a two-qubit gate.", BELL,
        "`00` and `11`, about half each. A key reads q[1] q[0].", "100 shots: `00`: 48, `11`: 44, `01`: 5, `10`: 3.",
        ("BELL.qasm",), made_by=by_hand()),
    "euroqexa-three-jobs": Readme(
        "euroqexa", "Three jobs in one manifest",
        "The X job, the Bell job, and the same Bell job again. It shows how a list of jobs runs in stages, and the "
        "Bell job sent twice shows the spread between two jobs of the same text.",
        ("Order 1: X", "Look at the result", "Orders 2 and 3: the same Bell job twice", "Compare the two"),
        "`1` every time for X; `00` and `11`, about half each, for each Bell job.", "", ("X.qasm", "BELL.qasm"),
        jobs=3, made_by=by_hand()),
    "euroqexa-ghz": Readme(
        "euroqexa", "A GHZ state of three qubits on Euro-Q-Exa",
        "H, then two CX: the state (|000> + |111>)/sqrt 2. All three qubits always agree.",
        ("Start: 000", "H on q[0]", "CX to q[1]", "CX to q[2]", "Measure", "000 and 111"),
        "`000` and `111`, about half each.", "", ("GHZ.qasm",), made_by=by_hand(LRZ)),
    "euroqexa-inverse": Readme(
        "euroqexa", "A circuit and its inverse on Euro-Q-Exa",
        "Prepare `011`, apply H and controlled RZ gates, then their inverse. A perfect machine undoes the whole "
        "middle, so no emulator is needed to know the answer. The site's compile may remove the middle: its job page "
        "on the portal shows what ran.",
        ("Start: 000", "X on q[0] and q[1]: 011", "H and controlled RZ", "Their inverse", "Measure", "011"),
        "`011` every time: q[0] and q[1] read 1. A key reads q[2] q[1] q[0].", "", ("INVERSE.qasm",),
        made_by=by_hand("From the MQSS adapter example `examples/inverse_unitary_test.py`, "
                        "Apache-2.0, with its loop written out.")),
    "vlq-one-qubit": Readme(
        "vlq", "One rotation on VLQ",
        "A PRX rotation by pi on one qubit: the smallest job on this machine. VLQ takes its own gates only, and "
        "does not compile.",
        ("Start: 0", "r(pi, 0)", "Measure", "1"),
        "`1` every time.", "100 shots: `1` in 97.", ("X.qasm",), made_by=by_hand()),
    "vlq-bell": Readme(
        "vlq", "A Bell pair on VLQ",
        "The qubits of VLQ do not touch each other: a two-qubit gate goes through a central resonator. So this text "
        "holds the machine's own gates: `r`, a rotation of one qubit; `move`, which moves a qubit's state into the "
        "resonator and back; and `cz`. VLQ does not compile, so the numbers count: `q[0]` to `q[23]` are the qubits "
        "and `q[24]` the resonator, and this can change with the calibration. The app checks the text against the "
        "site's table of that day before the job is made, and stops if it does not fit.",
        ("Start: 00", "r on q[0] and on q[1]", "Move q[0] into the resonator", "CZ of q[1] with the resonator",
         "Move q[0] back", "r on q[1]", "Measure", "00 and 11"),
        "`00` and `11`, about half each.", "", ("BELL.qasm",), made_by=by_hand()),
    "vlq-ghz": Readme(
        "vlq", "A GHZ state of five qubits on VLQ",
        "One qubit moves into the resonator, each other qubit takes a CZ with it between two rotations, and the first "
        "qubit moves back.",
        ("Start: 00000", "r on q[0]", "Move q[0] into the resonator", "Each other qubit: r, CZ with the resonator, r",
         "Move q[0] back", "Measure", "00000 and 11111"),
        "`00000` and `11111`, about half each.", "", ("GHZ.qasm",),
        made_by=by_hand("The circuit of the IT4I notebook `GHZ_example.ipynb`, in the star form of the "
                        "maker's notebook `DenebGHZ.ipynb`.")),
    "piastq-one-qubit": Readme(
        "piastq", "One rotation on Piast-Q",
        "An R rotation by pi on one trapped-ion qubit: the smallest job on this machine.",
        ("Start: 0", "R by pi", "Measure", "1"),
        "`1` every time.", "100 shots: `1` in 98.", ("X.json",), made_by=by_hand()),
    "piastq-bell": Readme(
        "piastq", "A Bell pair on Piast-Q",
        "One RXX gate at its largest angle: on trapped ions, a two-qubit gate makes the pair in one step. Keep a job "
        "at 200 shots or fewer: a job of 400 shots was taken and never started.",
        ("Start: 00", "One RXX gate", "Measure", "00 and 11"),
        "`00` and `11`, about half each.", "The same circuit, 200 shots: `00`: 113, `11`: 86, `10`: 1.",
        ("BELL.json",), made_by=by_hand()),
    "piastq-native": Readme(
        "piastq", "The three native operations of Piast-Q",
        "Piast-Q is a trapped-ion machine, reached through the PCSS broker, the service in front of it. It takes a "
        "list of three operations directly: RZ, a rotation about Z; R, a rotation about an axis in the XY plane; RXX, "
        "a rotation of two qubits that entangles them. This job uses each once. It is the default example of the "
        "maker's public API, and its angles are in units of pi.",
        ("Start: 00", "RZ on qubit 0", "R on qubit 1", "RXX on both", "Measure", "All four outcomes"),
        "`00`, `01`, `10` and `11`, about a quarter each.", "", ("NATIVE.json",),
        made_by=by_hand("From the default example of `POST /submit/{workspace}/{resource}` in the AQT "
                        "Public API 1.1.1.")),
}


def main() -> None:
    """Write the README and the three scripts of each folder."""
    for name, page in READMES.items():
        ExampleFolder(HERE / name, name).write_page(page)


if __name__ == "__main__":
    main()
