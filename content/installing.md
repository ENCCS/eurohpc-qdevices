# Install and first run

Install the app, then send one job. The app needs Python 3.11 or newer, with `httpx` and `cryptography`,
which come with it. It needs no client library of a site. A VLQ token still needs a LEXIS login ({doc}`vlq`).

## Install

With [pixi](https://pixi.sh), in a folder next to your manifests. A PyPI package needs Python from
conda-forge in the project first:

```bash
pixi init my-runs && cd my-runs
pixi add "python=3.12"
pixi add --pypi "eurohpc-qdevices @ git+https://github.com/ENCCS/eurohpc-qdevices"
pixi run qdevices --help
```

For a clone, give its absolute path with `--editable`:

```bash
pixi add --pypi --editable "eurohpc-qdevices @ file:///absolute/path/to/eurohpc-qdevices"
```

Once it is on PyPI, `pip install eurohpc-qdevices` in a virtual environment works too. Check the install
with `pixi run qdevices --version`. Below, `qdevices` means `pixi run qdevices`, or `qdevices` inside `pixi shell`.

## Where the app keeps its files

No flag and no environment variable moves these folders. The home folder is read from the user database,
not from `HOME`.

| Folder or file | What it holds |
|---|---|
| `~/.config/qdevices/qdevices.toml` | your projects and limits ({doc}`configuration`) |
| `~/.local/share/qdevices/records/<site>/<run>/` | the records of the runs ({ref}`records`) |
| `~/.local/share/qdevices/records/<site>/older_decisions.jsonl` | the decisions of `qdevices resolve` on records of other runners ({ref}`resolving`) |
| `~/.local/share/qdevices/reads/<site>/` | the reads of the machines by `qdevices check --live` |
| `~/.local/state/qdevices/` | the site locks, and the log of `qdevices unlock` ({ref}`one-host`) |

The app runs the same on a laptop and on a login node, but **drive one site from one host** ({ref}`one-host`).

## First run

Read {doc}`live-runs` and the page of your site first. These steps send one job to Euro-Q-Exa with
`examples/euroqexa-one-qubit`. For VLQ and Piast-Q, change the site name and the token variable.

1. Copy `examples/qdevices.toml` to `~/.config/qdevices/qdevices.toml`. Put your project in place of
   `MY-PROJECT` there and in the manifest ({doc}`configuration`, {doc}`manifests-and-records`).
2. Run the commands below. `FILE` is a file of your own that holds the token ({ref}`tokens`).
3. With several jobs, look at the first, then go on with
   `qdevices send MANIFEST --live --resume RECORD --max-order N` ({doc}`commands`).

```bash
qdevices dry-run examples/euroqexa-one-qubit/manifest.json    # offline, no token: "Dry run passed. Nothing was sent."
qdevices login euroqexa                                       # how to get the token, and the variable to set
set +x; export MQSS_TOKEN="$(cat FILE)"                       # LEXIS_TOKEN for VLQ, PCSS_API_KEY for Piast-Q
qdevices check euroqexa --live --manifest examples/euroqexa-one-qubit/manifest.json   # one read, stored; no job
qdevices dry-run examples/euroqexa-one-qubit/manifest.json    # again: the qubits against the read, and its age
qdevices send examples/euroqexa-one-qubit/manifest.json --live --max-order 1   # the first job alone
qdevices runs                                                 # one line for each record: find the record here
qdevices jobs RECORD                                          # one line for each order
qdevices usage                                                # totals by site and project
```

With `no_modify`, the second dry run also checks the gate names and the coupled pairs ({doc}`euroqexa`).
The send prints the path of the record, then each step. Step 1 edits these two files:

```{literalinclude} ../examples/qdevices.toml
:language: toml
:start-at: "[euroqexa]"
:end-before: "[vlq]"
```

```{literalinclude} ../examples/euroqexa-one-qubit/manifest.json
:language: json
```
