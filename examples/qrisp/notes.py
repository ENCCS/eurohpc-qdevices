"""What the README of each Qrisp example says: the title, the science, the steps, and what came back."""

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class Note:
    """One example: its title, what it does and why, the blocks of its diagram, and what came back."""

    title: str
    about: str
    steps: tuple[str, ...]
    back: str


LOST: Final = "By the rule of the tutorial the answer is not readable: it does not stand clear of the next keys."
NOTES: Final = {
    "BELL": Note(
        "A Bell pair",
        "H on q[0], then CX: the state (|00> + |11>)/sqrt 2. Each qubit alone reads 0 or 1 at random, and the two "
        "always agree. It is the smallest test of a two-qubit gate.",
        ("Start: 00", "H on q[0]", "CX from q[0] to q[1]", "Measure", "00 and 11"),
        "100 shots: `00`: 54, `11`: 41, and 5 on other keys."),
    "GHZ3": Note(
        "A GHZ state of three qubits",
        "H, then two CX: the state (|000> + |111>)/sqrt 2. All three qubits always agree.",
        ("Start: 000", "H on q[0]", "CX to q[1]", "CX to q[2]", "Measure", "000 and 111"),
        "100 shots: `000`: 46, `111`: 39."),
    "QFT3": Note(
        "The quantum Fourier transform",
        "The Fourier state of 5 on three qubits, built with H and phase gates, then Qrisp's inverse QFT, which gives "
        "the number back. The QFT is the last step of phase estimation, the method that reads energies from a "
        "simulation.",
        ("Start: 000", "H on all three", "Phases: the Fourier state of 5", "Inverse QFT", "Measure",
         "101, the number 5"),
        "1000 shots: `101`: 736."),
    "ABSTRACT_PARAMETER": Note(
        "A circuit with a symbol for an angle",
        "Qrisp builds the circuit with a symbol phi and binds it to pi/2 before the text is written: H on q[2], then "
        "a phase gate controlled on `00`. The text sent holds numbers only.",
        ("Start: 000", "H on q[2]", "Phase gate, controlled on 00, with phi = pi/2", "Measure", "000 and 100"),
        "1000 shots: `000`: 431, `100`: 337."),
    "QAOA_MAXCUT": Note(
        "One QAOA layer of MaxCut",
        "A phase on each edge of a graph of five nodes, then a rotation of each qubit, so bit strings that cut more "
        "edges gain weight. The angles are fixed, from a coarse search on an emulator.",
        ("Start: 00000", "H on all five", "A phase on each edge", "Rx on each qubit", "Measure", "The two best cuts"),
        "1000 shots: `11000`: 159, `00111`: 151, the two best cuts."),
    "TUTORIAL_QPE": Note(
        "Quantum phase estimation",
        "A register of three qubits reads the phase of two phase gates. Phase estimation is how an energy is read "
        "from exp(-iHt) in a simulation of a molecule. In a key, psi is q[0] q[1], and the phase is "
        "(q[2] + 2 q[3] + 4 q[4]) / 8, so `10001` is (10, 0.5).",
        ("Start: five qubits at 0", "H on all", "Phase gates, controlled by the three phase qubits",
         "Inverse QFT on the phase qubits", "Measure", "Four outcomes, a quarter each"),
        "1000 shots: `10111`: 155, `00110`: 143, `10001`: 137, `00000`: 136, the four outcomes expected."),
    "QUBO": Note(
        "One QAOA layer of a QUBO",
        "An optimisation over six bits, with a matrix of costs, in one QAOA layer with fixed angles. One layer lowers "
        "the mean cost, but it does not peak at the best string.",
        ("Start: six qubits at 0", "H on all six", "Rz and RZZ from the matrix of costs", "Rx on each qubit", "Measure",
         "One bit string most often"),
        "1000 shots: `100100`: 67 on top, then `110100`: 41. That key is the top of the ideal, at 0.20, with a cost of "
        "-17. The best string, `010001`, with a cost of -34, has an ideal share of 0.015 and read 19: one layer with "
        "fixed angles does not find it."),
    "CONSTRAINED_MIXER": Note(
        "A QAOA mixer that keeps a constraint",
        "From the allowed state `011`, a mixer that reaches only other allowed states, built with Qrisp's exact Grover "
        "routine. q[3] is a helper and ends at 0.",
        ("Start: 011", "Undo the preparation of the allowed states", "A phase on one state", "Prepare them again",
         "Measure", "Four allowed outcomes"),
        "1000 shots: `0100`: 171, `0110`: 130, `0001`: 110, and `0011`: 69, below the wrong keys `0111`: 76, `0101`: "
        "74 and `0000`: 71."),
    "QITE1": Note(
        "One step of quantum imaginary-time evolution",
        "Evolution in imaginary time lowers the energy of a state. One step for MaxCut on five nodes; its ideal peak "
        "is only 4.8 per cent. q[5] and q[6] are helpers and end at 0.",
        ("Start: five qubits at 0", "H on all five", "One step: evolutions under the cost and reflections", "Measure",
         "The best cuts, weakly"),
        f"1000 shots: `0000000`: 34, over 120 outcomes. {LOST}"),
    "ISING": Note(
        "A chain of six spins in a field",
        "Five Trotter steps of the Ising model, by Qrisp's `trotterization`: the method of `examples/hamiltonian/`, at "
        "a size that did not stay readable in this run.",
        ("Start: 000000", "One Trotter step: ZZ on each bond, X on each spin", "Five steps in all", "Measure",
         "A spread; 000000 most often"),
        f"1000 shots: `000001`: 55, `100001`: 50, `000000`: 47. {LOST}"),
    "SHOR13": Note(
        "Addition modulo 13",
        "8 + 8 modulo 13, the kind of arithmetic inside Shor's algorithm, in Qrisp's `QuantumModulus`.",
        ("Set the register to 8", "Add 8", "Compare with 13 and correct", "Measure", "The number 3"),
        f"1000 shots: `110000`: 31, over 64 outcomes; the answer, `000011`, read 21. {LOST}"),
    "BV4": Note(
        "Bernstein-Vazirani",
        "One query of an oracle gives all four bits of a hidden string, here 1011. The key reads the helper qubit "
        "first, then the string in reverse.",
        ("Start: 0000, helper 1", "H on all", "The oracle: CX to the helper from each 1 of the string", "H on all",
         "Measure", "The string 1011"),
        "1000 shots: `01101`: 662, then `11101`: 58."),
    "ADD_CONST": Note(
        "Addition on three bits",
        "3 + 3 by Qrisp's arithmetic, in place, with a carry. It is the same kind of step as in `shor13`, at a size "
        "that stays readable.",
        ("Set the register to 3", "QFT", "Phases that add 3", "Inverse QFT", "Measure", "The number 6"),
        "1000 shots: `110`: 713, then `100`: 110."),
    "GROVER3": Note(
        "Grover's search with one sharp answer",
        "Grover's search looks for one marked value among eight. The usual version finds it with a high chance; "
        "Qrisp's exact version (`grovers_alg` with `exact=True`) sets its angles so that a perfect machine finds it in "
        "every shot. Here the marked value is 6.",
        ("Start: 000", "H on all three", "The oracle: a phase on the winner", "The diffuser, with exact angles",
         "Measure", "The winner, 110"),
        "1000 shots: `110`: 351, then `100`: 128."),
    "HELLO": Note(
        "A word from the machine",
        "The first page of Qrisp's documentation, cut to one word: five bits a letter, 25 qubits, and only X gates. "
        "All 25 must read right for the word to come back, so this shows what a wide readout loses. Cut the key into "
        "five bits from the right, with a = 0: 00111 h, 00100 e, 01011 l, 01011 l, 01110 o.",
        ("Start: 25 qubits at 0", "X on each bit that is 1", "Measure all 25", "The word hello"),
        "1000 shots: the whole word in 523, and in the next key, with one bit flipped, 56."),
    "ISING2": Note(
        "Two spins in a field",
        "Five first-order Trotter steps of the Ising model, by Qrisp's `trotterization`. On two qubits all the steps "
        "make one two-qubit block, which 2 CX can make. The same model at 16 steps, with 32 two-qubit gates in the "
        "text, read `11` in 789 of 1000, against 783 here, so the site's compile very likely merged the steps: "
        "[`hamiltonian/two_spins`](../../hamiltonian/two_spins/README.md) holds both jobs.",
        ("Start: 00", "One Trotter step: ZZ, then X on each spin", "Five steps in all", "Measure", "11 most often"),
        "1000 shots: `11`: 783, then `00`: 95."),
}
