#!/usr/bin/env bash
# One example, from its own folder.
#   ./run.sh           a dry run: offline, no token, nothing sent
#   ./run.sh --login   how to get the token of the site
#   ./run.sh --live    one read of the machine, then the first job; needs your names in manifest.json and your token
#   ./run.sh --counts  what came back: the newest record of this example
set -u
cd "$(dirname "$0")" || exit 1

site=$(sed -n 's/^[[:space:]]*"site"[[:space:]]*:[[:space:]]*"\([a-z]*\)".*/\1/p' manifest.json | head -n 1)
case $site in
  euroqexa) token=MQSS_TOKEN ;;
  vlq) token=LEXIS_TOKEN ;;
  piastq) token=PCSS_API_KEY ;;
  *) echo "manifest.json names no known site" >&2; exit 2 ;;
esac

case "${1:-}" in
  ""|--login|--live|--counts) ;;
  *) echo "usage: $0 [--login|--live|--counts]" >&2; exit 2 ;;
esac

# The clone this folder is in, if any, and whether its Python can run through pixi.
root=$PWD
while [ "$root" != / ] && ! grep -qs '^name = "eurohpc-qdevices"' "$root/pyproject.toml"; do root=$(dirname "$root"); done
[ "$root" != / ] || root=
[ -n "$root" ] && command -v pixi >/dev/null 2>&1 && clone=1 || clone=0

in_clone() { pixi run --frozen --manifest-path "$root/pyproject.toml" "$@"; }

app() {
  if [ "$clone" -eq 1 ]; then
    in_clone qdevices "$@"
  elif command -v qdevices >/dev/null 2>&1; then
    qdevices "$@"
  else
    echo "qdevices is not installed: get pixi (https://pixi.sh) and run this in a clone of the repository" >&2
    return 127
  fi
}

case "${1:-}" in
  "")
    if [ "$clone" -eq 1 ]; then
      in_clone python "$root/examples/tools/dry_run.py" manifest.json || exit $?
    elif [ -n "$root" ] && python3 -c "import qdevices" 2>/dev/null; then
      python3 "$root/examples/tools/dry_run.py" manifest.json || exit $?
    else
      app dry-run manifest.json || exit $?
    fi
    echo "Next: README.md says what this example does, and how to send it." ;;
  --login)
    app login "$site" ;;
  --counts)
    if [ "$clone" -eq 1 ]; then in_clone python "$root/examples/tools/counts.py" manifest.json
    else echo "Run this in a clone of the repository, with pixi; or read the record the send printed." >&2; exit 2; fi ;;
  --live)
    if grep -q '"MY-' manifest.json; then
      echo "manifest.json still says MY-PROJECT or another MY- name: nothing was sent. See README.md." >&2
      exit 2
    fi
    if [ -n "${HOME:-}" ] && [ ! -e "$HOME/.config/qdevices/qdevices.toml" ]; then
      echo "You have no config yet: nothing was sent. From the top of the clone:" >&2
      echo "mkdir -p ~/.config/qdevices && cp examples/qdevices.toml ~/.config/qdevices/qdevices.toml" >&2
      echo "Then put your project in that copy. See README.md." >&2
      exit 2
    fi
    [ -n "${!token:-}" ] || { echo "$token is not set: nothing was sent. See: $0 --login" >&2; exit 2; }
    app check "$site" --live --manifest manifest.json || exit $?
    app send manifest.json --live --max-order 1 ;;
esac
