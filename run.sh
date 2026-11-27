#!/bin/sh
# Run Plywood Pro from source on macOS / Linux.
#   ./run.sh            your real data (data/plywoodpro.db)
#   ./run.sh --demo     sample data you can play with safely
#   ./run.sh test       run the automated tests
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Setting up (first run only)..."
  if command -v uv >/dev/null 2>&1; then
    uv venv -q --python 3.11 .venv && uv pip install -q --python .venv/bin/python -r requirements-dev.txt
  else
    python3 -m venv .venv && .venv/bin/python -m pip install -q -r requirements-dev.txt
  fi || { echo "Setup failed."; exit 1; }
fi
if [ "$1" = "test" ]; then shift; exec .venv/bin/python -m pytest -q "$@"; fi
exec .venv/bin/python main.py "$@"
