#!/usr/bin/env bash
# Send this example to the machine: one read, then its first job. This uses your award: see README.md first.
if [ $# -gt 0 ]; then
  echo "usage: $0    with no options: one read of the machine, then the first job. Nothing was sent now." >&2
  exit 2
fi
exec "$(dirname "$0")/run.sh" --live
