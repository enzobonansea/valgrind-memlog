#!/usr/bin/env bash
set -e
DIR="$(dirname "$0")"
: > "$DIR/out"
: > "$DIR/err"
exec 1>"$DIR/out" 2>"$DIR/err"
for d in "$DIR"/analysis/[0-9][0-9]_*/; do
    [ ! -f "$d/result.complete" ] && python3 "$DIR/run.py" "$(basename "$d")" || true
done
