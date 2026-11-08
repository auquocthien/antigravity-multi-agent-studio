#!/usr/bin/env bash
# Launcher script for Agy - Multi-Agent Studio
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export PYTHONPATH="$DIR:$PYTHONPATH"
export DISPLAY="${DISPLAY:-:0.0}"

# Prefer virtualenv python if present, otherwise fallback to system python3 or compiled binary
if [ -f "$DIR/.venv/bin/python3" ]; then
    exec "$DIR/.venv/bin/python3" "$DIR/src/main.py" "$@"
elif [ -f "$DIR/dist/linux-utility" ]; then
    exec "$DIR/dist/linux-utility" "$@"
else
    exec python3 "$DIR/src/main.py" "$@"
fi
