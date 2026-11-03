# Quantum phase estimation

A register of three qubits reads the phase of two phase gates. Phase estimation is how an energy is read from exp(-iHt) in a simulation of a molecule. In a key, psi is q[0] q[1], and the phase is (q[2] + 2 q[3] + 4 q[4]) / 8, so `10001` is (10, 0.5).

```mermaid
flowchart LR
    s0["Start: five qubits at 0"] --> s1["H on all"] --> s2["Phase gates, controlled by the three phase qubits"] --> s3["Inverse QFT on the phase qubits"] --> s4["Measure"] --> s5["Four outcomes, a quarter each"]
```

![The circuit of the job](circuit.png)

The circuit of the job as its file has it, drawn by qutip-qip: one-qubit gates in blue, two-qubit gates in orange, then the measurements. Its title names the job and says if anything is left out.

![The share of each key from each source](outcomes.png)

The share of each key, up to six keys and then the rest as other, from each source: a perfect machine (our emulator), QuTiP, Qrisp's emulator, and one run on the machine, with a bar of one shot error each way.

**What a perfect machine gives:** (psi, phase) (00, 0), (10, 0.5), (01, 0.125), (11, 0.625), a quarter each. `./emulate.sh` and the site print keys, with the highest qubit on the left: 00000: 0.250  00110: 0.250  10001: 0.250  10111: 0.250. Qrisp's own labels, as a Qrisp program prints them, read q[0] first, so a label and its key can look reversed. The line of Qrisp's emulator in `./emulate.sh` is in keys.

**What came back:** 1000 shots: `10111`: 155, `00110`: 143, `10001`: 137, `00000`: 136, the four outcomes expected. One run, on one day: it shows how much of the answer survived that day, not how good the machine is.

## Emulate it

Your computer computes what the machine would do: no account, no token, and nothing is sent. On your own computer:

```bash
git clone --depth 1 https://github.com/ENCCS/eurohpc-qdevices
cd eurohpc-qdevices/examples/qrisp/tutorial_qpe
./emulate.sh
```

It prints what a perfect machine gives, then the stored results of Qrisp's emulator and of QuTiP, with no noise, then what the machine gave if this example has run. Add a simple model of noise, which is ours and not a model of any machine, with `./emulate.sh --noise 0.03 --readout 0.03`. It needs Python 3.8 or later, or [pixi](https://pixi.sh).

Or in your browser, with nothing to install: [![Run on Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=doc/tree/examples/all_examples.ipynb). The first start can take some minutes. That page holds all the examples: put `qrisp/tutorial_qpe` in `NAME` under Choose one.

## Send it to the machine

This part is for people with an account at the site, and it uses their award.

```mermaid
flowchart LR
    s0["./run.sh: a check, offline"] --> s1["./submit.sh: asks the machine for its state, no job yet"] --> s2["The job goes, with a record on disk"] --> s3["The site compiles the text and runs the shots"] --> s4["./run.sh --counts"]
```

1. Run `./run.sh`: a dry run, with no token, that sends nothing. It needs [pixi](https://pixi.sh), on Linux x86-64 or an Apple Silicon Mac, and a clone of the repository. It checks against `examples/qdevices.toml` while the manifest says `MY-`, then against your config, and it counts each measurement as a gate.
2. The first time, from the top of the clone: `mkdir -p ~/.config/qdevices && cp examples/qdevices.toml ~/.config/qdevices/qdevices.toml`. The app reads its settings there. Put your own names in that copy and in `manifest.json` here, in place of `MY-PROJECT`.
3. Set your token, which is never printed: `set +x; export MQSS_TOKEN="$(cat FILE)"`, where FILE is the file that holds your token. `./run.sh --login` says how to get one. A token is personal: never hand it to anyone else.
4. Run `./submit.sh`. It reads the machine once, sends the job, waits for it, and stores the counts in a record.
5. Run `./run.sh --counts` to see what came back.

## The files

| File | What it is |
|---|---|
| `TUTORIAL_QPE.qasm` | the circuit in OpenQASM 2; the site compiles it |
| `manifest.json` | what to send: the site, your project, and for each job its file, its SHA-256 and its shots |
| `emulate.sh` | emulates the example; nothing is sent |
| `qrisp_emulated.json` | the share of each key on Qrisp's emulator, stored, so `./emulate.sh` needs no Qrisp |
| `qutip_emulated.json` | the share of each key on QuTiP, with no noise, stored, so `./emulate.sh` needs no QuTiP |
| `circuit.png` | the picture of the circuit above, drawn by qutip-qip |
| `outcomes.png` | the chart of the outcomes above; from the top of the clone, `pixi run --manifest-path examples/qrisp/pixi.toml pictures` draws both again |
| `run.sh` | checks the example offline for a real send; also `--login` and `--counts` |
| `submit.sh` | sends the example to the machine |
| `results.json` | the counts of one run on the machine, with no job id and no date |

Written by `examples/qrisp/write_manifests.py` from `programs.py`. To change the circuit, change the function, and from the top of the clone run `pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples`: a text changed by hand no longer matches its SHA-256.

More: the [Euro-Q-Exa page](https://enccs.github.io/eurohpc-qdevices/euroqexa/) of the manual.
