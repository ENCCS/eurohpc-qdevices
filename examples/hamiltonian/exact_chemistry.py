"""The reference curves of H2 by PySCF: restricted Hartree-Fock and full configuration interaction (FCI), in each basis.

PySCF stays out of every lock: use `pixi exec`, from this folder. The tutorial reads the stored numbers, so it needs
no PySCF. This writes the key "pyscf" of reference_curve.json and leaves its other keys as they are. It took one to
five minutes on a laptop at two threads, nearly all of it in cc-pVQZ:

    OMP_NUM_THREADS=2 pixi exec --spec "pyscf=2.14.0" python exact_chemistry.py
"""

from typing import Final

import pyscf
from hydrogen import STORED, keep_numbers, stored_numbers
from pyscf import fci, gto, lib, scf

LENGTHS: Final = (0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.735, 0.7414, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4, 1.6, 1.8,
                  2.0, 2.2, 2.6, 3.0, 3.5, 4.0)
BASES: Final = ("sto-3g", "6-31g", "cc-pvdz", "cc-pvtz", "cc-pvqz")
DECIMALS: Final = 8
MEMORY_MB: Final = 4000


def molecule(length: float, basis: str) -> gto.Mole:
    """H2 at a bond length in angstrom."""
    return gto.M(atom=f"H 0 0 0; H 0 0 {length}", basis=basis, unit="Angstrom", verbose=0, max_memory=MEMORY_MB)


def energies(length: float, basis: str) -> tuple[float, float]:
    """Restricted Hartree-Fock and FCI at one length. Either one not converged stops the script."""
    mean_field = scf.RHF(molecule(length, basis))
    mean_field.conv_tol, mean_field.conv_tol_grad, mean_field.max_cycle = 1e-12, 1e-8, 1000
    mean_field.kernel()
    solver = fci.FCI(mean_field)
    solver.conv_tol, solver.conv_tol_residual, solver.max_cycle = 1e-12, 1e-7, 500
    energy = solver.kernel()[0]
    if not (mean_field.converged and solver.converged):
        raise RuntimeError(f"not converged: {basis} at {length} angstrom")
    return round(float(mean_field.e_tot), DECIMALS), round(float(energy), DECIMALS)


def curves(basis: str) -> dict:
    """All lengths in one basis, with its spin orbitals: the qubits before any symmetry."""
    rows = [energies(length, basis) for length in LENGTHS]
    return {"spin_orbitals": 2 * molecule(LENGTHS[0], basis).nao_nr(),
            "restricted_hartree_fock": [row[0] for row in rows], "fci": [row[1] for row in rows]}


def main() -> None:
    """Write the numbers, and keep the keys that come from elsewhere."""
    held = stored_numbers() if STORED.exists() else {}
    held["pyscf"] = {"version": pyscf.__version__, "bohr_in_angstrom": lib.param.BOHR, "decimals": DECIMALS,
                     "lengths_angstrom": LENGTHS, "bases": {basis: curves(basis) for basis in BASES}}
    keep_numbers(held)


if __name__ == "__main__":
    main()
