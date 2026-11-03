# What serves the examples

You do not need to open this folder to use an example: each example folder has its own README and scripts.

| File | What it is |
|---|---|
| `emulate.py` | the command: what a perfect machine, Qrisp's emulator and QuTiP (both stored), a noise model if asked and the machine gave for each job of a manifest |
| `circuit.py`, `texts.py`, `gates.py` | the emulator, in Python's standard library: a state vector and a simple noise model; reading a circuit; the gates |
| `qrisp_emulator.py`, `write_qrisp_emulated.py` | the same circuits on Qrisp's emulator; only the first imports Qrisp; the second writes each folder's `qrisp_emulated.json`: `pixi run --manifest-path examples/qrisp/pixi.toml qrisp-emulated` |
| `qutip_emulator.py`, `write_qutip_emulated.py` | the same circuits on QuTiP, by qutip-qip's gates, with no noise; only the first imports QuTiP; the second writes each folder's `qutip_emulated.json`: `pixi run --manifest-path examples/qrisp/pixi.toml qutip-emulated` |
| `write_qutip_scripts.py` | writes each folder's `emulate_qutip.py`, the example in QuTiP code, one line per gate, from the gates `gate_steps` of `qutip_emulator.py` gives, so each script gives the stored shares: `pixi run --manifest-path examples/qrisp/pixi.toml qutip-scripts`; name folders after it to write those alone |
| `write_qrisp_scripts.py` | writes each folder's `emulate_qrisp.py`, the example in Qrisp code, one line per gate, from the calls `qrisp_calls` of `qrisp_emulator.py` gives, so each script gives the stored shares: `pixi run --manifest-path examples/qrisp/pixi.toml qrisp-scripts`; name folders after it to write those alone |
| `overview.py` | all the examples in one table and one chart, for `all_examples.ipynb` |
| `pictures.py`, `write_pictures.py` | a circuit drawn by qutip-qip, and bars of the share of each key from each source of a folder; for notebooks and tests, never for `emulate.sh`; the second writes each folder's `circuit.png`, of the first job or of the job `DRAWN` in `readme.py` names, and `outcomes.png`: `pixi run --manifest-path examples/qrisp/pixi.toml pictures` |
| `palette.py` | the house colours of the pictures and of the charts of the notebooks |
| `emulate_one.sh`, `run_one.sh`, `submit_one.sh` | the models of each folder's `emulate.sh`, `run.sh` and `submit.sh` |
| `dry_run.py`, `counts.py` | what `run.sh` calls for its dry run and for `--counts` |
| `readme.py`, `example_folder.py` | the README of a folder; a folder on disk, with its manifest, README and scripts |
| `folders.py` | what the READMEs of the folders written by hand say: `pixi run python examples/tools/folders.py` writes them |
