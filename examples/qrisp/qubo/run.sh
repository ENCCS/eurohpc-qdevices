#!/usr/bin/env bash
# One example on Euro-Q-Exa. No flag: a dry run, offline, nothing sent. --live: one read, then one job.
# Needs `qdevices` on PATH; --live also needs MQSS_TOKEN and your project in manifest.json.
set -u
cd "$(dirname "$0")" || exit 1
case "${1:-}" in
  "") exec qdevices dry-run manifest.json ;;
  --live) ;;
  *) echo "usage: $0 [--live]" >&2; exit 2 ;;
esac
if grep -q '"project": "MY-PROJECT"' manifest.json; then
  echo "manifest.json still says MY-PROJECT: nothing was sent." >&2
  echo "Make your own copy: pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples --project YOURS --out my-runs" >&2
  exit 2
fi
[ -n "${MQSS_TOKEN:-}" ] || { echo "MQSS_TOKEN is not set: nothing was sent. See: qdevices login euroqexa" >&2; exit 2; }
qdevices check euroqexa --live --manifest manifest.json || exit $?
exec qdevices send manifest.json --live --max-order 1
