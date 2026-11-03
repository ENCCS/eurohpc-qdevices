#!/usr/bin/env bash
# Open the tutorial on your own computer. No account, no token, and nothing is sent.
cd "$(dirname "$0")" || exit 1
if command -v pixi >/dev/null 2>&1; then
  exec pixi exec --spec "python=3.12" --spec jupyterlab --spec numpy --spec scipy --spec matplotlib-base \
    --spec "qutip=5.3.1" -- jupyter lab tutorial.ipynb "$@"
fi
echo "Get pixi (https://pixi.sh) and run this again; or, with pip: pip install jupyterlab numpy scipy matplotlib qutip qutip-qip" >&2
echo "then: jupyter lab tutorial.ipynb" >&2
exit 2
