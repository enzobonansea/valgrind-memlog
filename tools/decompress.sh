#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <folder>" >&2
    exit 1
fi

FOLDER="${1%/}"
ARCHIVE="${FOLDER}.tar.xz"

if [ ! -f "$ARCHIVE" ]; then
    echo "Error: '$ARCHIVE' not found" >&2
    exit 1
fi

for cmd in pv pixz; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' is not installed" >&2
        exit 1
    fi
done

echo "Decompressing '$ARCHIVE' ($(du -h "$ARCHIVE" | cut -f1))"
pv "$ARCHIVE" | pixz -d | tar -xv
echo "Done: extracted to '$FOLDER'"
