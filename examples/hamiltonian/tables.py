"""The tables of the tutorial, as text: the exact answer, the product formulas, the noisy emulator, and hydrogen."""

from math import pi

from chain import Steps, T, closed_form
from circuit import Circuit
from hydrogen import Curve
from matrices import Formula, exact, shares, start
from molecule import Molecule, PhaseEstimation, atom_energy, minimum
from reference import EQUILIBRIUM, KCAL, Reference

KEYS = ("001", "010", "100")


def routes() -> str:
    """The share of each key at four times, by the closed form and by a matrix exponential."""
    rows = [f"{'t':>4}  closed form 001, 010, 100     matrix exponential"]
    for name, t in (("0", 0.0), ("T/2", T / 2), ("T", T), ("2T", 2 * T)):
        closed, by_matrix = closed_form(t), shares(exact(t) @ start())
        rows.append(f"{name:>4}  " + " ".join(f"{closed[k]:.3f}" for k in KEYS) + "           "
                    + " ".join(f"{by_matrix.get(k, 0):.3f}" for k in KEYS))
    return "\n".join(rows)


def formulas(steps: tuple[int, ...] = (1, 2, 4, 8, 16)) -> str:
    """For each number of steps at T, at both orders: the error, the share of 100, and the two-qubit gates."""
    rows = [f"{'N':>3} | error, order 1, order 2 | share of 100, order 1, order 2 | two-qubit gates, order 1, order 2"]
    for n in steps:
        one, two = Formula(T, n, 1), Formula(T, n, 2)
        arrival_of = [shares(f.matrix() @ start()).get("100", 0) for f in (one, two)]
        rows.append(f"{n:>3} | {one.error():>13.4f} {two.error():>9.4f} | {arrival_of[0]:>20.4f} {arrival_of[1]:>9.4f} "
                    f"| {4 * n:>23} {4 * n + 2:>9}")
    return "\n".join(rows)


def arrival(steps: int, noise: float, readout: float, shots: int = 4000) -> float:
    """The share of the key 100 at T on the emulator, order 2."""
    return Circuit.of_text(Steps(T, steps).text()).sample(shots, noise, readout).get("100", 0) / shots


def rise_and_fall(levels: tuple[float, ...] = (0.01, 0.03, 0.06), readout: float = 0.03,
                  steps: tuple[int, ...] = (1, 2, 3, 4, 6, 8, 12)) -> str:
    """The share of 100 at T on the emulator, for each number of steps and level of noise."""
    rows = [f"{'N':>3} {'2q':>4} {'perfect':>8} " + " ".join(f"{f'noise {level}':>11}" for level in levels)]
    for n in steps:
        circuit = Circuit.of_text(Steps(T, n).text())
        noisy = " ".join(f"{arrival(n, level, readout):>11.3f}" for level in levels)
        rows.append(f"{n:>3} {circuit.two_qubit:>4} {circuit.shares()['100']:>8.3f} {noisy}")
    return "\n".join(rows)


def well() -> str:
    """The minimum and the depth below two atoms: in STO-3G, and as published, where one atom has -0.5 exactly."""
    lowest, best = minimum(), Reference.load()
    published = best.minimum
    depth, published_depth = 2 * atom_energy() - lowest.exact, -1 - published.energy
    too_deep = depth - published_depth
    return "\n".join([f"{'':<16} {'length':>7} {'energy':>9} {'depth':>7}",
                      f"{'exact in STO-3G':<16} {lowest.length:>7.4f} {lowest.exact:>9.4f} {depth:>7.4f}",
                      f"{'published':<16} {published.bohr * best.bohr:>7.4f} {published.energy:>9.4f} "
                      f"{published_depth:>7.4f}",
                      f"STO-3G is too deep by {too_deep:.4f} hartree, {too_deep * KCAL:.1f} kcal/mol"])


def against_closed_form(run: Curve) -> str:
    """Each length of a run against the closed form of molecule.py: reading, share, and the shift of the steps."""
    rows = [f"{'length':>6} {'reading, gates':>15} {'closed form':>12} {'share, gates':>13} {'closed form':>12} "
            f"{'shift':>9}"]
    for point in run.points:
        molecule = Molecule(point.length)
        closed = PhaseEstimation(molecule, run.bits, run.steps)
        shift = molecule.levels(run.steps)[0][0] - molecule.levels()[0][0]
        rows.append(f"{point.length:>6} {point.energy:>15.4f} {closed.reading():>12.4f} {point.share:>13.4f} "
                    f"{closed.shares()[point.phase]:>12.4f} {shift:>+9.5f}")
    return "\n".join(rows)


def more_bits(length: float = EQUILIBRIUM, bits: tuple[int, ...] = (6, 8, 10, 12, 14, 16), steps: int = 3) -> str:
    """By the closed form, with no gates: what more bits read at one length, against STO-3G and the published."""
    molecule, best = Molecule(length), Reference.load().published(length)
    rows = [f"{'bits':>4} {'grid step':>10} {'reading':>9} {'above exact in STO-3G':>22} {'above published':>16}"]
    for n in bits:
        read = PhaseEstimation(molecule, n, steps).reading()
        rows.append(f"{n:>4} {2 * pi / 2 ** n:>10.5f} {read:>9.5f} {read - molecule.exact:>+22.5f} "
                    f"{read - best:>+16.5f}")
    return "\n".join(rows)


def readings(length: float = 2.6, bits: tuple[int, ...] = (6, 7, 8, 9, 10)) -> str:
    """By the closed form, at a stretched bond: the top reading against the lowest strong peak, at each size."""
    molecule = Molecule(length)
    rows = [f"At {length} angstrom: exact energy {molecule.exact:.3f}, squared overlap {molecule.overlap:.3f}.",
            f"{'bits':>4} {'top reading':>12} {'lowest strong peak':>19}"]
    rows += [f"{n:>4} {PhaseEstimation(molecule, n).top():>12.3f} {PhaseEstimation(molecule, n).reading():>19.3f}"
             for n in bits]
    return "\n".join(rows)
