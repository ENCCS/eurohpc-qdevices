# Programs written in Qrisp

Sixteen small programs in [Qrisp](https://qrisp.eu), for Euro-Q-Exa. Each has a folder of its own with its `README.md`, `emulate.sh` and `run.sh`. In a clone of the repository:

```bash
cd examples/qrisp/grover3
./emulate.sh
```

Each of them has run on Euro-Q-Exa with this app (`qft3` twice, at 100 and 1000 shots; the 1000 is shown). One run each, on one day: it shows how much of each answer survived that day, not how good the machine is. *Readable* means that the ideal top key is the top of the counts, and at least twice the next wrong key.

| Folder | What it sends | Two-qubit gates in the text | What came back |
|---|---|---|---|
| [`bell`](bell/README.md) | a Bell pair | 1 | readable |
| [`ghz3`](ghz3/README.md) | a GHZ state of three qubits | 2 | readable |
| [`bv4`](bv4/README.md) | Bernstein-Vazirani, a hidden string of four bits | 3 | readable |
| [`hello`](hello/README.md) | a word on 25 qubits, with no two-qubit gate | 0 | readable |
| [`abstract_parameter`](abstract_parameter/README.md) | a circuit with a symbol for an angle | 6 | readable |
| [`qft3`](qft3/README.md) | the quantum Fourier transform | 9 | readable |
| [`ising2`](ising2/README.md) | two spins in a field, five Trotter steps | 10 | readable |
| [`add_const`](add_const/README.md) | 3 + 3 on three bits | 12 | readable |
| [`qaoa_maxcut`](qaoa_maxcut/README.md) | one QAOA layer of MaxCut | 12 | readable |
| [`tutorial_qpe`](tutorial_qpe/README.md) | phase estimation, three bits | 21 | readable |
| [`grover3`](grover3/README.md) | Grover's search, one winner of eight | 24 | readable |
| [`constrained_mixer`](constrained_mixer/README.md) | a QAOA mixer that keeps a constraint | 26 | three of the four answers |
| [`qubo`](qubo/README.md) | one QAOA layer of a QUBO | 36 | not readable: top key right, 1.6 times the next |
| [`ising`](ising/README.md) | six spins in a field, five Trotter steps | 50 | not readable by the rule |
| [`qite1`](qite1/README.md) | one step of imaginary-time evolution | 54 | not readable by the rule |
| [`shor13`](shor13/README.md) | 8 + 8 modulo 13 | 132 | not readable by the rule |

## Send several at once

```bash
examples/qrisp/send_all.sh                                # inside pixi shell, with your config: a dry run of each
pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples --project YOURS --out my-runs
examples/qrisp/send_all.sh --live --dir my-runs qft3 qubo  # only these, each once
```

`send_all.sh --live` with no names sends all sixteen. Name the folders you want. It needs `qdevices` on your PATH, so run it inside `pixi shell`.

## Add your own program

1. Add a function that returns a Qrisp variable to `programs.py`, a line to `PROGRAMS`, and a note to `notes.py`.
2. Run `pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples`. It writes one folder for each program, with its text, its manifest, its README and its `run.sh`.

## The files here

| File | What it is |
|---|---|
| `programs.py` | the programs, and what a perfect machine would give |
| `pages.py` | the eight programs that follow pages of the Qrisp documentation |
| `notes.py` | what the README of each program says |
| `qasm2.py` | writes a Qrisp circuit as an OpenQASM 2 text |
| `write_manifests.py` | writes every folder |
| `send_all.sh` | sends several folders |
| `pixi.toml`, `pixi.lock` | the environment with Qrisp, so the app's own environment holds none |

More: [Circuits written in Qrisp](https://enccs.github.io/eurohpc-qdevices/qrisp/) in the manual.
