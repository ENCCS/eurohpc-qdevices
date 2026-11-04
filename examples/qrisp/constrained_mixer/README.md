# A QAOA mixer that keeps a constraint

From the allowed state `011`, a mixer that reaches only other allowed states, built with Qrisp's exact Grover routine. q[3] is a helper and ends at 0.

```mermaid
flowchart LR
    s0["Start: 011"] --> s1["Undo the preparation of the allowed states"] --> s2["A phase on one state"] --> s3["Prepare them again"] --> s4["Measure"] --> s5["Four allowed outcomes"]
```

![The circuit of the job](circuit.png)

The circuit of the job as its file has it, drawn by qutip-qip: one-qubit gates in blue, two-qubit gates in orange, then the measurements. Its title names the job and says if anything is left out.

![The share of each key from each source](outcomes.png)

The share of each key, up to six keys and then the rest as other, from each source: a perfect machine (our emulator), QuTiP, Qrisp's emulator, and one run on the machine, with a bar of one shot error each way.

**What a perfect machine gives:** 100, 110, 001 and 011, a quarter each. `./emulate.sh` and the site print keys, with the highest qubit on the left: 0001: 0.250  0011: 0.250  0100: 0.250  0110: 0.250. Qrisp's own labels, as a Qrisp program prints them, read q[0] first, so a label and its key can look reversed. The line of Qrisp's emulator in `./emulate.sh`, and what `emulate_qrisp.py` prints, are in keys.

**What came back:** 1000 shots: `0100`: 171, `0110`: 130, `0001`: 110, and `0011`: 69, below the wrong keys `0111`: 76, `0101`: 74 and `0000`: 71. One run, on one day: it shows how much of the answer survived that day, not how good the machine is.

## Emulate it

Your computer computes what the machine would do: no account, no token, and nothing is sent. On your own computer:

```bash
git clone --depth 1 https://github.com/ENCCS/eurohpc-qdevices
cd eurohpc-qdevices/examples/qrisp/constrained_mixer
./emulate.sh
```

It prints what a perfect machine gives, then the stored results of Qrisp's emulator and of QuTiP, with no noise, then what the machine gave if this example has run. Add a simple model of noise, which is ours and not a model of any machine, with `./emulate.sh --noise 0.03 --readout 0.03`. It needs Python 3.8 or later, or [pixi](https://pixi.sh).

Or in your browser, with nothing to install: [![Run on Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=lab/tree/examples/all_examples.ipynb). The first start can take some minutes. That page holds all the examples: put `qrisp/constrained_mixer` in `NAME` under Choose one. Binder opens JupyterLab, where File > New > Terminal gives a terminal at the top of the clone: `cd examples/qrisp/constrained_mixer && ./emulate.sh` runs this example there as on your own computer.

`emulate_qutip.py` and `emulate_qrisp.py` are this example in QuTiP code and in Qrisp code, gate by gate, to read. Run in this folder, each prints what its emulator gives, with no noise: `python emulate_qutip.py` where QuTiP and qutip-qip are installed, `python emulate_qrisp.py` where Qrisp is, as on Binder. From the top of a clone of your own, on Linux x86-64 or an Apple Silicon Mac: `pixi run --manifest-path examples/qrisp/pixi.toml python examples/qrisp/constrained_mixer/emulate_qutip.py`, and the same with `emulate_qrisp.py`; the first run installs QuTiP and Qrisp, about 1 GB.

No need to write OpenQASM yourself: write the circuit in QuTiP or in Qrisp, as these two files do, and `--qasm` prints its OpenQASM 2 text for Euro-Q-Exa, which compiles it. In this folder, `python emulate_qutip.py --qasm CONSTRAINED_MIXER > mine.qasm`, or the same with `emulate_qrisp.py`, puts the text of the job CONSTRAINED_MIXER in `mine.qasm`. With pixi, run `pixi run --manifest-path examples/qrisp/pixi.toml python examples/qrisp/constrained_mixer/emulate_qutip.py --qasm CONSTRAINED_MIXER > examples/qrisp/constrained_mixer/mine.qasm` from the top of the clone, then come back here. To send it, put `mine.qasm` and its SHA-256 in `manifest.json` in place of the file and the SHA-256 of that job (`shasum -a 256 mine.qasm` on a Mac, `sha256sum mine.qasm` on Linux).

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
| `CONSTRAINED_MIXER.qasm` | the circuit in OpenQASM 2; the site compiles it |
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

Written by `examples/qrisp/write_manifests.py` from the function `constrained_mixer` of `pages.py`, listed in `programs.py`. To change the circuit, change that function, and from the top of the clone run `pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples`: a text changed by hand no longer matches its SHA-256. After a change, the stored results, the two scripts and the pictures here still show the old circuit: [After a change](../../README.md#after-a-change) says how to make them again.

More: the [Euro-Q-Exa page](https://enccs.github.io/eurohpc-qdevices/euroqexa/) of the manual.
