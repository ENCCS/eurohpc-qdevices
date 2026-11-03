# Two spins in a field: the short start

[![Run on Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=lab/tree/examples/hamiltonian/two_spins/two_spins.ipynb)

The short start to Hamiltonian simulation: one short notebook, [`two_spins.ipynb`](two_spins.ipynb). Two spins of the Ising model in a transverse field, `H = -Z0 Z1 - 1.2 (X0 + X1)`, start in `00` and evolve to `t = 2 pi/2.6`, a time at which `01` and `10` are zero and `11` holds 0.874. The notebook solves the model exactly in QuTiP, writes the evolution as Trotter steps of CX, RZ and H, builds the same circuit in Qrisp, and reads two runs on Euro-Q-Exa: 5 steps, and 16.

Why this model: it is a model of magnets such as LiHoF4 and CoNb2O6 in a field across their axis; quantum annealing changes its field over time; and one Trotter step, a short slice of the evolution written as gates, has the shape of one layer of QAOA, the quantum approximate optimisation algorithm. The notebook cites the papers. Two spins are solved exactly on any laptop, and the magnets, annealing and QAOA need many spins: the point here is to learn the steps that carry over. The [long tutorial](../tutorial.ipynb) goes on to three qubits and to the hydrogen molecule.

```mermaid
flowchart LR
    s0["Start: 00"] --> s1["One Trotter step: CX, RZ, CX for ZZ; H, RZ, H for X on each spin"] --> s2["5 steps, or 16"] --> s3["Measure"] --> s4["11 most often"]
```

![The circuit of the first job](circuit.png)

The circuit of the first job as its file has it, drawn by qutip-qip: one-qubit gates in blue, two-qubit gates in orange, then the measurements. Its title names the job and says if anything is left out.

![The share of each key from each source](outcomes.png)

The share of the key a perfect machine gives most, for each job, from each source: a perfect machine (our emulator), QuTiP, Qrisp's emulator, and one run on the machine, with a bar of one shot error each way.

**What a perfect machine gives:** `11` at 0.866 for STEPS5 and at 0.877 for STEPS16; with no Trotter error, 0.874. A key reads q[1] q[0]. At this time the exact evolution puts nothing on `01` and `10`; 5 steps put 0.013 on each.

**What came back:** 1000 shots each, from runs of these same texts; STEPS5 was sent as `qrisp/ising2`. STEPS5: `11`: 783, `00`: 95, `01`: 67, `10`: 55. STEPS16: `11`: 789, `00`: 113, `01`: 53, `10`: 45. The two read the same within the shot error, about 0.013, though STEPS16 has 32 CX in its text and STEPS5 has 10. On two qubits all the steps make one two-qubit block, which 2 CX can make, so the site's compile very likely merged them; the circuit that ran has not been read. One run, on one day: it shows how much of the answer survived that day, not how good the machine is.

## Emulate it

Your computer computes what the machine would do: no account, no token, and nothing is sent. On your own computer:

```bash
git clone --depth 1 https://github.com/ENCCS/eurohpc-qdevices
cd eurohpc-qdevices/examples/hamiltonian/two_spins
./emulate.sh
```

It prints what a perfect machine gives, then the stored results of Qrisp's emulator and of QuTiP, with no noise, then what the machine gave if this example has run. Add a simple model of noise, which is ours and not a model of any machine, with `./emulate.sh --noise 0.03 --readout 0.03`. It needs Python 3.8 or later, or [pixi](https://pixi.sh).

Or in your browser, with nothing to install: [![Run on Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=lab/tree/examples/hamiltonian/two_spins/two_spins.ipynb), the notebook of this folder. The first start can take some minutes. [`all_examples.ipynb`](../../all_examples.ipynb) holds all the examples: put `hamiltonian/two_spins` in `NAME` under Choose one. It opens in JupyterLab, where File > New > Terminal gives a terminal: `cd examples/hamiltonian/two_spins && ./emulate.sh` runs this example there as on your own computer.

## Send it to the machine

This part is for people with an account at the site, and it uses their award.

```mermaid
flowchart LR
    s0["./run.sh: a check, offline"] --> s1["./submit.sh: asks the machine for its state, no job yet"] --> s2["The job goes, with a record on disk"] --> s3["The site compiles the text and runs the shots"] --> s4["./run.sh --counts"]
```

1. Run `./run.sh`: a dry run, with no token, that sends nothing. It needs [pixi](https://pixi.sh), on Linux x86-64 or an Apple Silicon Mac, and a clone of the repository. It checks against `examples/qdevices.toml` while the manifest says `MY-`, then against your config, and it counts each measurement as a gate.
2. The first time, from the top of the clone: `mkdir -p ~/.config/qdevices && cp examples/qdevices.toml ~/.config/qdevices/qdevices.toml`. The app reads its settings there. Put your own names in that copy and in `manifest.json` here, in place of `MY-PROJECT`.
3. Set your token, which is never printed: `set +x; export MQSS_TOKEN="$(cat FILE)"`, where FILE is the file that holds your token. `./run.sh --login` says how to get one. A token is personal: never hand it to anyone else.
4. Run `./submit.sh`. It reads the machine once and sends order 1 alone, so you can look at it first. It then prints `Go on with: qdevices send ... --max-order N`. Start `pixi shell` at the top of the clone, come back here, and run that line with N = 2; no order goes twice.
5. Run `./run.sh --counts` to see what came back.

## The files

| File | What it is |
|---|---|
| `STEPS5.qasm` | the circuit in OpenQASM 2; the site compiles it |
| `STEPS16.qasm` | the circuit in OpenQASM 2; the site compiles it |
| `manifest.json` | what to send: the site, your project, and for each job its file, its SHA-256 and its shots |
| `emulate.sh` | emulates the example; nothing is sent |
| `qrisp_emulated.json` | the share of each key on Qrisp's emulator, stored, so `./emulate.sh` needs no Qrisp |
| `qutip_emulated.json` | the share of each key on QuTiP, with no noise, stored, so `./emulate.sh` needs no QuTiP |
| `circuit.png` | the picture of the circuit above, drawn by qutip-qip |
| `outcomes.png` | the chart of the outcomes above; from the top of the clone, `pixi run --manifest-path examples/qrisp/pixi.toml pictures` draws both again |
| `run.sh` | checks the example offline for a real send; also `--login` and `--counts` |
| `submit.sh` | sends the example to the machine |
| `results.json` | the counts of one run on the machine, with no job id and no date |
| `two_spins.ipynb` | the notebook: the model, the gates, Qrisp, the run, where the model is used, and what the run shows |
| `spins.py` | the model in QuTiP: its levels, the exact evolution, the Trotter steps, the chart |
| `by_qrisp.py` | the same in Qrisp: the function that writes the texts, and Qrisp's emulator |
| `trotter.py` | the steps as a text in Python alone, for other fields and steps |
| `machine.py` | the counts as shares with shot errors, and the simple model of the notebook |
| `write_two_spins.py` | writes this folder |

This folder is written by `write_two_spins.py`; its texts come from `ising2` in `examples/qrisp/programs.py`. To change a job, change it there and, from the top of the clone, run `pixi run --manifest-path examples/qrisp/pixi.toml two-spins`: a text changed by hand no longer matches its SHA-256.

More: the [Euro-Q-Exa page](https://enccs.github.io/eurohpc-qdevices/euroqexa/) of the manual.
