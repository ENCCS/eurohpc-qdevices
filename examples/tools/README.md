# What serves the examples

You do not need to open this folder to use an example: each example folder has its own README and scripts.

| File | What it is |
|---|---|
| `emulate.py` | the command: what a perfect machine, Qrisp's emulator and QuTiP (both stored), a noise model if asked and the machine gave for each job of a manifest |
| `circuit.py`, `texts.py`, `gates.py` | the emulator, in Python's standard library: a state vector and a simple noise model; reading a circuit; the gates |
| `qrisp_emulator.py`, `write_qrisp_emulated.py` | the same circuits on Qrisp's emulator; only the first imports Qrisp; the second writes each folder's `qrisp_emulated.json`: `pixi run --manifest-path examples/qrisp/pixi.toml qrisp-emulated`; name folders after it to write those alone |
| `qutip_emulator.py`, `write_qutip_emulated.py` | the same circuits on QuTiP, by qutip-qip's gates, with no noise; only the first imports QuTiP; the second writes each folder's `qutip_emulated.json`: `pixi run --manifest-path examples/qrisp/pixi.toml qutip-emulated`; name folders after it to write those alone |
| `write_qutip_scripts.py` | writes each folder's `emulate_qutip.py`, the example in QuTiP code, gate by gate, from the gates that `gate_steps` in `qutip_emulator.py` gives, so each script gives the stored shares: `pixi run --manifest-path examples/qrisp/pixi.toml qutip-scripts`; name folders after it to write those alone |
| `write_qrisp_scripts.py` | writes each folder's `emulate_qrisp.py`, the example in Qrisp code, gate by gate, from the calls that `qrisp_calls` in `qrisp_emulator.py` gives, so each script gives the stored shares: `pixi run --manifest-path examples/qrisp/pixi.toml qrisp-scripts`; name folders after it to write those alone |
| `script_parts.py` | what the two writers of the scripts share: the keys line, an angle as code, `top`, the main block, the comment lines of the gates and the check of a job name; it imports neither emulator |
| `script_qasm.py` | the part of the two scripts of a Euro-Q-Exa folder that writes OpenQASM 2 (`--qasm`): qutip-qip's writer, with a way round what qutip-qip 0.4.2 does not write (H, CZ, the semicolon after each measurement and the point in a number such as 1.0e-05), and `qrisp/qasm2.py` for Qrisp |
| `overview.py` | all the examples in one table and one chart, for `all_examples.ipynb` |
| `scripts_shown.py` | the first job of a folder's `emulate_qutip.py` and `emulate_qrisp.py`, and what each prints when run, for Choose one in `all_examples.ipynb`; the QuTiP job of `qrisp/hello`, on 25 qubits, is left to a terminal |
| `pictures.py`, `write_pictures.py` | a circuit drawn by qutip-qip, and bars of the share of each key from each source of a folder; for notebooks and tests, never for `emulate.sh`; the second writes each folder's `circuit.png`, of the first job or of the job `DRAWN` in `readme.py` names, and `outcomes.png`: `pixi run --manifest-path examples/qrisp/pixi.toml pictures`; name folders after it to write those alone |
| `palette.py` | the house colours of the pictures and of the charts of the notebooks |
| `emulate_one.sh`, `run_one.sh`, `submit_one.sh` | the models of each folder's `emulate.sh`, `run.sh` and `submit.sh` |
| `dry_run.py`, `counts.py` | what `run.sh` calls for its dry run and for `--counts` |
| `readme.py`, `example_folder.py` | the README of a folder; a folder on disk, with its manifest, README and scripts |
| `folders.py` | what the READMEs of the folders written by hand say: `pixi run python examples/tools/folders.py` writes them |
