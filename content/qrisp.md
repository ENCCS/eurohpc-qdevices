# Circuits written in Qrisp

Write the circuit with [Qrisp](https://qrisp.eu) as an OpenQASM 2 file, make a manifest, and go on as with
any other example. Qrisp only makes the files; the app does not need it. These examples have run on
Euro-Q-Exa with this app; the table below says which answers stayed readable. The dry run checks the file offline; it does not run the site's compiler.

| Site | Takes an OpenQASM 2 text from Qrisp? | Why |
|---|---|---|
| Euro-Q-Exa | Yes, without `no_modify` | The site compiles an OpenQASM 2 text for the machine ({doc}`euroqexa`) |
| VLQ | No: the dry run says "not an OpenQASM 3 text", "not native on VLQ" | It takes OpenQASM 3 in its native gates (`r` or `prx`, `cz`, `move`) through its resonator, and does not compile ({doc}`vlq`) |
| Piast-Q | No: the dry run says "not an operation list of the broker" | It takes the broker's operation list (`R`, `RZ`, `RXX`, `MEASURE`), not OpenQASM ({doc}`piastq`) |

Do not set `no_modify` for these texts. They use `h`, `cx`, `rz` and `rx`, and with `no_modify` the site compiles
nothing, so every gate must be one the machine lists. The dry run checks the gates against a saved read
and refuses any other.

## The examples

`examples/qrisp/` has a folder for each program, each with its own README, `emulate.sh`, `run.sh` and `submit.sh`, the script that wrote them, and `send_all.sh` for several at once. Each
manifest has two keys of its own, `made_with` and `ideal`, which the app copies to the start line of the
record. Some are small checks; eight follow pages of the Qrisp documentation (`pages.py`), each with its angles fixed. The ideal
answers are in Qrisp's labels.

The [table in `examples/qrisp/`](https://github.com/ENCCS/eurohpc-qdevices/blob/main/examples/qrisp/README.md) lists
them, with what stayed readable. `bell` and `ghz3` take 100 shots, the others 1000. One run each, on one day: it shows how
much of each answer survived that day, not how good the machine is. The site's compile can very likely merge gates, so
the size of a text is not always the cost of a job: `ising2` read the same at 5 steps and at 16.

To emulate any of them with no account: `./emulate.sh` in its folder, or the page
[all_examples.ipynb](https://mybinder.org/v2/gh/ENCCS/eurohpc-qdevices/main?urlpath=lab/tree/examples/all_examples.ipynb) on Binder.
{doc}`hamiltonian` is the tutorial on `trotterization`.

On Euro-Q-Exa a key of `counts` reads q[n-1] ... q[0], while Qrisp's label of a variable reads q[0] first:
reverse a key to compare it with `get_measurement` ({doc}`rules`).

```bash
examples/qrisp/ising/run.sh                    # one example: a dry run, offline, no token
examples/qrisp/send_all.sh                     # inside pixi shell, with your config: a dry run of each
pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples --project YOURS --out my-runs
my-runs/ising/run.sh --live                    # your own copy of one example: one read, then one job
examples/qrisp/send_all.sh --live --dir my-runs             # all, smallest first, one job each
examples/qrisp/send_all.sh --live --dir my-runs qft3 qubo   # only these
```

With `--live` the script needs `MQSS_TOKEN`, reads the machine once (`qdevices check euroqexa --live`), then
runs `qdevices send MANIFEST --live --max-order 1` for each and stops at the first failure, with the command
to go on. It refuses a manifest that still says `MY-PROJECT`.

## Your own program

In a clone of the repository, the pixi workspace in `examples/qrisp/` adds the latest Qrisp to the
app; the default environment does not have it. Outside pixi, `pip install qrisp` in the environment of the
app works too. Qrisp needs Python 3.11 to 3.13 and installs packages of its own.

```bash
pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples                                   # writes examples/qrisp/*/ again
pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples --project YOURS --shots 200 --out my-runs
```

1. Add a function that returns a Qrisp variable to `examples/qrisp/programs.py`, a line to `PROGRAMS`, and a note
   to `examples/qrisp/notes.py`, which its README takes.
2. Run the script again. It writes one folder for each program, with the text and a manifest of one job
   for Euro-Q-Exa, with its SHA-256.
3. To collect several programs in one run, copy their job lines into one manifest, with the orders 1 to N
   ({doc}`manifests-and-records`).

## How the text is written

`examples/qrisp/qasm2.py` reads Qrisp's own circuit data and writes one line per instruction. It does not
use Qrisp's text export (`to_qasm2`, `qasm`, `to_qasm3` of `QuantumCircuit`), as in Qrisp 0.9.10 that export
hands the circuit to a package of another framework.

```python
qc = qv.qs.compile()        # the circuit of the session of the variable qv
qc.measure(qc.qubits)       # every qubit into its own classical bit, in order
qc = qc.transpile()         # break composite gates (QFT, swap, cp) down
text = to_qasm2(qc)         # examples/qrisp/qasm2.py
```

The text has one register `q` of all qubits and one register `c` of all classical bits, and only gates of
the original `qelib1.inc`. It is not optimised and no layout is chosen: the site does that. Any other gate,
or an angle that is still a symbol, stops the writer with its name, and nothing is written.

| Qrisp | OpenQASM 2 |
|---|---|
| `x`, `y`, `z`, `h`, `s`, `t`, `cx`, `cy`, `cz` | the same name |
| `s_dg`, `t_dg` | `sdg`, `tdg` |
| `rx`, `ry`, `rz`, `u3` | the same name, with the angles in radians |
| `p` | `rz`: the two differ by a global phase only, which no count shows |
| `sx`, `sx_dg` | `rx(pi/2)`, `rx(-pi/2)`: a global phase only |
| `measure`, `barrier`, `reset` | the same statement |
| `gphase`, `qb_alloc`, `qb_dealloc` | left out: a global phase, and Qrisp's marks of allocation |

**Sources:** the Qrisp documentation <https://qrisp.eu> and the source of Qrisp 0.9.10 on PyPI; the gate list
of the original `qelib1.inc`, <https://github.com/openqasm/openqasm/blob/OpenQASM2.x/examples/qelib1.inc>.
