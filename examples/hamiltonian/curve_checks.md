# The checks behind the curve of H2

This file holds the details that Section 9 of the tutorial leaves out. Lengths are in angstrom and energies in hartree. The tests are `tests/test_hydrogen_*.py`.

## The states of STO-3G

In STO-3G two electrons have 6 states, and symmetry splits them into blocks. The start reaches one block of two states: both electrons in the bonding orbital (the sum of the two functions), or both in the antibonding orbital (their difference). So for the ground state FCI comes down to a $2\times2$ matrix. `molecule.py` builds it from the integrals of the Gaussians (`integrals.py`), with NumPy alone, in a few milliseconds at most on a laptop.

## The closed form of phase estimation

With $b$ bits, a level at phase $\varphi$ gives the grid point $m/2^b$ the share $|c_k|^2 \sin^2(\pi 2^b \delta) / (4^b \sin^2(\pi\delta))$, with $\delta = \varphi - m/2^b$. By this closed form the nearest grid point always holds at least $(2/\pi)^2 = 0.405$ of the share of a level. The overlap here is at least 0.504, so the peak of the ground level holds at least 0.204.

A level above zero wraps round the grid to a low reading. With the 3 steps, at 0.5 Å, the upper level lies at +0.2425 for the electrons alone. It wraps round to -6.041, and the grid of 8 bits reads it at -6.038 with a share of 0.0052. The limit of 0.1 in the rule leaves it out.

## Where the rule of reading holds

The rule is safe when the gap between the two levels spans a few grid steps. That gap is 0.57 at its smallest: 2.9 grid steps at 5 bits, and 1.4 at 4 bits. From 5 bits up the rule read the ground level at every length we tried, up to 15 Å. At 4 bits it did so up to 10 Å, with little margin, and beyond that it reads the upper level. At 3 bits, with steps of 0.785, it lands more than half a step from the ground level between 1.84 and 2.22 Å.

## The gates against the closed form

The closed form of `molecule.py`, with the 3 steps of the product formula, checks the gates. The stored run gives this, from `tables.against_closed_form(Curve.stored())`:

```text
length  reading, gates  closed form  share, gates  closed form     shift
   0.5         -1.0524      -1.0524        0.9705       0.9699  +0.00062
0.7414         -1.1270      -1.1270        0.5681       0.5680  +0.00047
   1.1         -1.0897      -1.0897        0.4795       0.4796  +0.00032
   1.4         -1.0210      -1.0210        0.7492       0.7486  +0.00022
   1.8         -0.9577      -0.9577        0.7121       0.7116  +0.00010
   2.6         -0.9255      -0.9255        0.3361       0.3361  +0.00001
   3.0         -0.9281      -0.9281        0.4530       0.4527  +0.00000
   4.0         -0.9231      -0.9231        0.2796       0.2796  +0.00000
```

The readings agree in every row. The shares at the two readings agree to 0.00057. That gap comes from how Qrisp's emulator ends, not from the gates: it drops each share under 0.00001, scales the rest to sum to 1, rounds them to 5 decimals and scales them again. These steps applied to the closed form give every stored share. Gates made in the same way, on a double-precision state vector, agree with the closed form to better than $10^{-10}$, at 6 bits at two lengths and at 8 bits at one (`tests/test_hydrogen_gates.py`). *shift* is how far the 3 steps of the product formula move the ground level. It falls from 0.00062 at 0.5 Å to under 0.00001 at 3 Å, far below the grid step of 0.0245.

## The published values

Their stated accuracy is $10^{-13}$ hartree or better from 0.35 to 4 Å, so they are exact for every digit the tutorial prints. Pachucki names the adiabatic, nonadiabatic, relativistic and quantum electrodynamics effects as further terms. Sims and Hagstrom agree with them to better than $4\times10^{-12}$ hartree at every length both list, from 0.4 to 6 bohr.

The published rows are in bohr, and we convert with 1 bohr = 0.52917721 Å, the value PySCF uses. Where no row has a length we interpolate: a polynomial of $E - 1/r$, with $r$ in bohr, through the 8 nearest rows. $1/r$ is the repulsion of the nuclei, which a polynomial follows poorly. With one row left out, the polynomial gives that row to within 0.000002.

## Two uses of chemical accuracy

Section 9 uses chemical accuracy for energy differences, after Motta and Rice. The one energy difference in the tutorial is the depth of the well, and STO-3G has it 18.6 kcal/mol too deep against the published curve. McArdle, Endo et al. (Rev. Mod. Phys. 92, 015003, [arXiv:1808.10402](https://arxiv.org/abs/1808.10402)) apply the term to the error at every point of the potential energy surface. For two atoms that surface is this curve, and that is what the right-hand columns of the table of bases show.

## To make the numbers again

```bash
OMP_NUM_THREADS=2 pixi exec --spec "pyscf=2.14.0" python exact_chemistry.py     # the key "pyscf" of reference_curve.json
```

`exact_chemistry.py` writes the key `pyscf` of `reference_curve.json`, and `with_qrisp.py` writes its key `emulated`. The key `published` holds the rows of Table IV of Pachucki's paper and the minimum from its abstract. A new run on another machine may change the last digits of a stored share, and then the digest in `tests/test_hydrogen_curve.py` must change with the file.
