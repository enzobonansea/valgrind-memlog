#!/usr/bin/env bash
set -e
DIR="$(dirname "$0")"
for d in "$DIR"/analysis/[0-9][0-9]_*/; do
    [ ! -f "$d/result.complete" ] && python3 "$DIR/run.py" "$(basename "$d")" || true
done
