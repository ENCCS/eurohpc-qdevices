# The jobs of the Hamiltonian tutorial

The jobs of the tutorial in `examples/hamiltonian/`: start there. One excitation crosses three qubits under `H = (1/2) sum (XX + YY)`, and arrives in full at `T = pi/sqrt 2`. The jobs are CONTROL (no evolution), MAIN and QRISP (the same evolution as two texts), REPEAT (the text of MAIN again, to see how far two jobs of one circuit differ), HALF (at T/2), BACK (at 2T, when it has returned), ZERO (the same gates with no excitation), STEPS1, STEPS4, STEPS8 (other numbers of Trotter steps) and ORDER1 (first order).

```mermaid
flowchart LR
    s0["Start: 001"] --> s1["Rx(pi/2) on all"] --> s2["MAIN: five bonds in turn, q0-q1, q1-q2, q0-q1, q1-q2, q0-q1"] --> s3["Rx(-pi/2) on all"] --> s4["Measure"] --> s5["100, on arrival"]
```

![The circuit of the job MAIN](circuit.png)

The circuit of the job MAIN as its file has it, drawn by qutip-qip: one-qubit gates in blue, two-qubit gates in orange, then the measurements. Its title names the job and says if anything is left out.

![The share of each key from each source](outcomes.png)

The share of the key a perfect machine gives most, for each job, from each source: a perfect machine (our emulator), QuTiP, Qrisp's emulator, and one run on the machine, with a bar of one shot error each way.

**What a perfect machine gives:** `100` at 0.970 for MAIN, QRISP and REPEAT; `001` for CONTROL, and at 0.988 for BACK; `000` for ZERO. A key reads q[2] q[1] q[0]. `manifest.json` holds the shares of each job.

**What came back:** `100` in 641 of 1000 for MAIN, 661 for REPEAT, 696 for QRISP; 381, 474 and 190 for 1, 4 and 8 steps. The tutorial reads them all. One run, on one day: it shows how much of the answer survived that day, not how good the machine is.

## Emulate it

Your computer computes what the machine would do: no account, no token, and nothing is sent. On your own computer:

```bash
git clone --depth 1 https://github.com/ENCCS/eurohpc-qdevices
cd eurohpc-qdevices/examples/hamiltonian/state_transfer
./emulate.sh
```

It prints what a perfect machine gives, then the stored results of Qrisp's emulator and of QuTiP, with no noise, then what the machine gave if this example has run. Add a simple model of noise, which is ours and not a model of any machine, with `./emulate.sh --noise 0.03 --readout 0.03`. It needs Python 3.8 or later, or [pixi](https://pixi.sh).

Or in your browser, with nothing to install: [![Run on Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=lab/tree/examples/all_examples.ipynb). The first start can take some minutes. That page holds all the examples: put `hamiltonian/state_transfer` in `NAME` under Choose one. Binder opens JupyterLab, where File > New > Terminal gives a terminal at the top of the clone: `cd examples/hamiltonian/state_transfer && ./emulate.sh` runs this example there as on your own computer.

`emulate_qutip.py` and `emulate_qrisp.py` are this example in QuTiP code and in Qrisp code, gate by gate, to read. Run in this folder, each prints what its emulator gives, with no noise: `python emulate_qutip.py` where QuTiP and qutip-qip are installed, `python emulate_qrisp.py` where Qrisp is, as on Binder. From the top of a clone of your own, on Linux x86-64 or an Apple Silicon Mac: `pixi run --manifest-path examples/qrisp/pixi.toml python examples/hamiltonian/state_transfer/emulate_qutip.py`, and the same with `emulate_qrisp.py`; the first run installs QuTiP and Qrisp, about 1 GB.

No need to write OpenQASM yourself: write the circuit in QuTiP or in Qrisp, as these two files do, and `--qasm` prints its OpenQASM 2 text for Euro-Q-Exa, which compiles it. In this folder, `python emulate_qutip.py --qasm MAIN > mine.qasm`, or the same with `emulate_qrisp.py`, puts the text of the job MAIN in `mine.qasm`; with no job name, `--qasm` prints the text of each job, after a line `// NAME`, to read: a file to send holds one job. With pixi, run `pixi run --manifest-path examples/qrisp/pixi.toml python examples/hamiltonian/state_transfer/emulate_qutip.py --qasm MAIN > examples/hamiltonian/state_transfer/mine.qasm` from the top of the clone, then come back here. To send it, put `mine.qasm` and its SHA-256 in `manifest.json` in place of the file and the SHA-256 of that job, and of each other job that names the same file (`shasum -a 256 mine.qasm` on a Mac, `sha256sum mine.qasm` on Linux).

## Send it to the machine

This part is for people with an account at the site, and it uses their award.

```mermaid
flowchart LR
    s0["./run.sh: a check, offline"] --> s1["./submit.sh: asks the machine for its state, no job yet"] --> s2["The job goes, with a record on disk"] --> s3["The site compiles the text and runs the shots"] --> s4["./run.sh --counts"]
```

1. Run `./run.sh`: a dry run, with no token, that sends nothing. It needs [pixi](https://pixi.sh), on Linux x86-64 or an Apple Silicon Mac, and a clone of the repository. It checks against `examples/qdevices.toml` while the manifest says `MY-`, then against your config, and it counts each measurement as a gate.
2. The first time, from the top of the clone: `mkdir -p ~/.config/qdevices && cp examples/qdevices.toml ~/.config/qdevices/qdevices.toml`. The app reads its settings there. Put your own names in that copy and in `manifest.json` here, in place of `MY-PROJECT`.
3. Set your token, which is never printed: `set +x; export MQSS_TOKEN="$(cat FILE)"`, where FILE is the file that holds your token. `./run.sh --login` says how to get one. A token is personal: never hand it to anyone else.
4. Run `./submit.sh`. It reads the machine once and sends order 1 alone, so you can look at it first. It then prints `Go on with: qdevices send ... --max-order N`. Start `pixi shell` at the top of the clone, come back here, and run that line with N = 11; no order goes twice.
5. Run `./run.sh --counts` to see what came back.

## The files

| File | What it is |
|---|---|
| `*.qasm` | the circuit in OpenQASM 2; the site compiles it |
| `manifest.json` | what to send: the site, your project, and for each job its file, its SHA-256 and its shots |
| `emulate.sh` | emulates the example; nothing is sent |
| `qrisp_emulated.json` | the share of each key on Qrisp's emulator, stored, so `./emulate.sh` needs no Qrisp |
| `qutip_emulated.json` | the share of each key on QuTiP, with no noise, stored, so `./emulate.sh` needs no QuTiP |
| `emulate_qutip.py` | this example in QuTiP code, gate by gate; running it prints what QuTiP gives |
| `emulate_qrisp.py` | this example in Qrisp code, gate by gate; running it prints what Qrisp's emulator gives |
| `circuit.png` | the picture of the circuit above, drawn by qutip-qip |
| `outcomes.png` | the chart of the outcomes above |
| `run.sh` | checks the example offline for a real send; also `--login` and `--counts` |
| `submit.sh` | sends the example to the machine |
| `results.json` | the counts of one run on the machine, with no job id and no date |

Written by `examples/hamiltonian/write_chain.py`. To change a job, change it there and run the script again. After a change, the stored results, the two scripts and the pictures here still show the old circuit: [After a change](../../README.md#after-a-change) says how to make them again.

More: the [Euro-Q-Exa page](https://enccs.github.io/eurohpc-qdevices/euroqexa/) of the manual.
