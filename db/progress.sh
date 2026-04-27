#!/usr/bin/env bash
# Snapshot of plow progress: completed result.csvs out of 34, latest log lines,
# current spill on disk, current free memory.
set -u

PLOW_LOG=${PLOW_LOG:-/tmp/plow.log}
ANALYSIS=/home/enzo/valgrind-memlog/db/analysis
TMP=/home/enzo/valgrind-memlog/db/.duckdb_tmp

done_count=$(ls "$ANALYSIS"/*/result.csv 2>/dev/null | wc -l)
running=$(ps -eo args | awk '/^python3 run\.py [^ ]/ {print $3; exit}')
spill=$(du -sh "$TMP" 2>/dev/null | awk '{print $1}')
mem=$(free -h | awk 'NR==2 {printf "mem=%s/%s ", $3, $2} NR==3 {printf "swap=%s/%s", $3, $2}')

echo "Done   : $done_count/34 result.csv files"
echo "Running: ${running:-(none)}"
echo "Spill  : ${spill:-0}    $mem"
echo
echo "Last log lines:"
grep -E '^>>> |row\(s\) in|FAILED|ALL DONE' "$PLOW_LOG" 2>/dev/null | tail -8
