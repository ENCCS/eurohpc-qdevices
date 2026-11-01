#!/usr/bin/env bash
# The Qrisp examples on Euro-Q-Exa, one job each, smallest text first. Needs `qdevices` on PATH.
#   send_all.sh                          a dry run of each manifest: no token, no network, nothing sent
#   send_all.sh --live [NAME ...]        needs MQSS_TOKEN; one check, then one send each; stops at the first failure
#   send_all.sh --live --dir my-runs     your own copy: pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples --project YOURS --out my-runs
set -u

dir=$(dirname "$0")
live=0
names=
while [ $# -gt 0 ]; do
  case $1 in
    --live) live=1 ;;
    --dir) [ $# -ge 2 ] || { echo "--dir needs a folder" >&2; exit 2; }; dir=$2; shift ;;
    -h|--help) sed -n '2,5s/^# //p' "$0"; exit 0 ;;
    -*) echo "unknown flag: $1" >&2; exit 2 ;;
    *) names="$names $1" ;;
  esac
  shift
done
for n in $names; do
  [ -f "$dir/$n/manifest.json" ] || { echo "no manifest: $dir/$n/manifest.json" >&2; exit 2; }
done

# The chosen manifests, one per line, the smallest text first.
sized() {
  for m in "$dir"/*/manifest.json; do
    [ -f "$m" ] || continue
    n=${m%/manifest.json}; n=${n##*/}
    if [ -n "$names" ]; then case "$names " in *" $n "*) ;; *) continue ;; esac; fi
    echo "$(( $(cat "${m%manifest.json}"*.qasm | wc -c) )) $m"
  done
}
list=$(sized | sort -n | cut -d' ' -f2-)
[ -n "$list" ] || { echo "no manifest in $dir" >&2; exit 2; }
left=
while IFS= read -r m <&3; do n=${m%/manifest.json}; left="$left ${n##*/}"; done 3<<EOF
$list
EOF
# The first chosen manifest that still says MY-PROJECT, if any.
held=$(echo "$list" | while IFS= read -r m; do grep -q '"project": "MY-PROJECT"' "$m" && { echo "$m"; break; }; done)
own_copy() {
  echo "$held still says MY-PROJECT. Make your own copy:"
  echo "  pixi run --manifest-path examples/qrisp/pixi.toml qrisp-examples --project YOURS --out my-runs"
  echo "  $0 --live --dir my-runs"
}

if [ $live -eq 0 ]; then
  status=0
  while IFS= read -r m <&3; do
    echo "== qdevices dry-run $m"
    qdevices dry-run "$m" 3<&- || status=1
    echo "would send: qdevices send $m --live --max-order 1"
  done 3<<EOF
$list
EOF
  echo "Nothing was sent."
  if [ -n "$held" ]; then own_copy; else echo "To send: $0 --live --dir $dir$left"; fi
  exit $status
fi

[ -z "$held" ] || { echo "Nothing was sent." >&2; own_copy >&2; exit 2; }
[ -n "${MQSS_TOKEN:-}" ] || { echo "--live needs MQSS_TOKEN set (see qdevices login euroqexa)" >&2; exit 2; }

first=$(echo "$list" | head -n 1)
echo "== qdevices check euroqexa --live --manifest $first"
qdevices check euroqexa --live --manifest "$first" || {
  code=$?; echo "Stopped at the check (exit $code). To go on: $0 --live --dir $dir$left" >&2; exit $code; }

while IFS= read -r m <&3; do
  n=${m%/manifest.json}; n=${n##*/}
  left=${left#" $n"}
  echo "== qdevices send $m --live --max-order 1"
  qdevices send "$m" --live --max-order 1 3<&- || {
    code=$?
    echo "Stopped at $n (exit $code). Settle it as qdevices says above; to go on with the rest:" >&2
    if [ -n "$left" ]; then echo "  $0 --live --dir $dir$left" >&2; else echo "  (it was the last one)" >&2; fi
    exit $code
  }
done 3<<EOF
$list
EOF
echo "Done: one send for each manifest, each with exit 0."
