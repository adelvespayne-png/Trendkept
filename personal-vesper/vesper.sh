#!/usr/bin/env bash
# The same two steps as the Windows .bat files, for a Mac or a Linux box.
#
#   ./vesper.sh          start Vesper and open the map
#   ./vesper.sh setup    first run: build the environment and a token
#
# Everything lands in a .venv beside this file, so uninstalling is deleting
# the folder.
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
  echo "No python3 on this machine. Install it, then run this again." >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "  Making a private environment..."
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip --quiet
  echo "  Installing what Vesper needs. This is the slow part."
  .venv/bin/python -m pip install -r requirements.txt
fi

if [ "${1:-}" = "setup" ]; then
  exec .venv/bin/python -m vesper.launch --setup
fi

echo
echo "  Starting Vesper. The map will open in your browser shortly."
echo "  Ctrl-C to stop her."
echo
exec .venv/bin/python -m vesper.launch "$@"
