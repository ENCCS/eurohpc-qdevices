#!/usr/bin/env bash
# Emulate this example on your own computer: no account, no token, and nothing is sent.
#   ./emulate.sh                                       a perfect machine, the stored results of Qrisp and QuTiP, and what the machine gave if it ran
#   ./emulate.sh --noise 0.03 --readout 0.03           with a simple model of noise; it is not a model of any machine
set -u
here=$(dirname "$0") && cd "$here" || exit 1
root=$PWD
while [ "$root" != / ] && [ ! -f "$root/examples/tools/emulate.py" ]; do root=$(dirname "$root"); done
if [ "$root" = / ]; then
  echo "Run this in a clone of the repository: https://github.com/ENCCS/eurohpc-qdevices" >&2
  exit 2
fi
if command -v pixi >/dev/null 2>&1; then
  pixi exec --spec "python=3.12" -- python -V >/dev/null &&
    exec pixi exec --spec "python=3.12" -- python "$root/examples/tools/emulate.py" manifest.json "$@"
  echo "pixi could not get Python 3.12; trying python3." >&2
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$root/examples/tools/emulate.py" manifest.json "$@"
fi
echo "This needs Python 3.8 or later, or pixi (https://pixi.sh)." >&2
exit 2
