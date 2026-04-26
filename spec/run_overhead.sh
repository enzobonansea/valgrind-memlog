#!/bin/bash
# Run overhead measurements for 4 benchmarks × 3 configs
# Extracts SPEC's own workload elapsed time

cd /usr/cpu2017 && . ./shrc

BENCHMARKS="508.namd_r 521.wrf_r 527.cam4_r 554.roms_r"
CONFIGS="native lackey memlog-noop"
OUTFILE="/tmp/overhead_timing.txt"

> "$OUTFILE"

for config in $CONFIGS; do
    for bm in $BENCHMARKS; do
        echo "=== Running $config / $bm ==="

        runcpu --action=run --config=${config}.cfg --size=test --noreportable --nopower --iterations=1 "$bm" 2>&1 | tail -5

        # Find the latest log file
        LATEST_LOG=$(ls -t /usr/cpu2017/result/CPU2017.*.log | head -1)

        # Extract workload elapsed time
        ELAPSED=$(grep "Workload elapsed time" "$LATEST_LOG" | tail -1 | sed 's/.*= \([0-9.]*\) seconds/\1/')

        # Convert to milliseconds using awk (no bc in container)
        ELAPSED_MS=$(echo "$ELAPSED" | awk '{printf "%d", $1 * 1000}')

        # Map config name to label
        case "$config" in
            native)     LABEL="NATIVE" ;;
            lackey)     LABEL="LACKEY" ;;
            memlog-noop) LABEL="MEMLOG" ;;
        esac

        echo "${LABEL} ${bm}: ${ELAPSED_MS}ms" | tee -a "$OUTFILE"
    done
done

echo ""
echo "=== RESULTS ==="
cat "$OUTFILE"
