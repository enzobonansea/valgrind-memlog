#!/bin/bash
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <folder>" >&2
    exit 1
fi

FOLDER="${1%/}"

if [ ! -d "$FOLDER" ]; then
    echo "Error: '$FOLDER' is not a directory" >&2
    exit 1
fi

for cmd in pv pixz; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' is not installed" >&2
        exit 1
    fi
done

SIZE=$(du -sb "$FOLDER" | cut -f1)
OUTPUT="${FOLDER}.tar.xz"

echo "Compressing '$FOLDER' ($(numfmt --to=iec "$SIZE")) -> $OUTPUT"
tar -cv "$FOLDER" | pv -s "$SIZE" | pixz > "$OUTPUT"
echo "Done: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
