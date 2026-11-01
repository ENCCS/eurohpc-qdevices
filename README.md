# eurohpc-qdevices

A small app that sends a fixed list of circuits to a EuroHPC quantum computer, one job at a time, and
keeps an exact record of what was sent and what came back. For **Euro-Q-Exa** (LRZ), **VLQ**
(IT4Innovations) and **Piast-Q** (PCSS). It never cancels a job, never sends one twice, and never stores
or prints a token.

**To get onto the machines**, follow the ENCCS lesson
[EuroHPC JU quantum devices and HPC-QC access in practice](https://enccs.github.io/eurohpc-quantum-devices-access-hpcqc/).

## Install and first run

```bash
pixi init my-runs && cd my-runs
pixi add "python=3.12"
pixi add --pypi "eurohpc-qdevices @ git+https://github.com/ENCCS/eurohpc-qdevices"
```

Put your projects and limits in `~/.config/qdevices/qdevices.toml`; start from `examples/qdevices.toml`.
`examples/` has a manifest for each site.

```bash
qdevices dry-run MANIFEST                          # offline: the files, their SHA-256, shots, project
qdevices login SITE                                # how to get the token
qdevices check SITE --live --manifest MANIFEST     # one read of the machine, no job
qdevices send MANIFEST --live --max-order 1        # the first job alone
```

## Manual, tests and licence

The manual is in `content/`; `pixi run docs` builds it. Read its Live runs page and the page of your site
before a live run.

```bash
pixi run -e test test     # offline, with fake sites
pixi run --manifest-path examples/qrisp/pixi.toml test    # the same, and the Qrisp examples made again
```

Code: MIT (`LICENSE.code`). Manual: CC BY-SA 4.0 (`LICENSE`). Citation: `CITATION.cff`.
