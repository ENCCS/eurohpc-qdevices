#!/usr/bin/env bash
# Open the page with all the examples on your own computer. No account, no token, and nothing is sent.
cd "$(dirname "$0")" || exit 1
if command -v pixi >/dev/null 2>&1; then
  exec pixi exec --spec "python=3.12" --spec jupyterlab --spec matplotlib-base -- jupyter lab all_examples.ipynb "$@"
fi
echo "Get pixi (https://pixi.sh) and run this again; or, with pip: pip install jupyterlab matplotlib" >&2
echo "then: jupyter lab all_examples.ipynb" >&2
exit 2
