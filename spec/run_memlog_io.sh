#!/bin/bash
# Run Memlog with real file I/O for 4 benchmarks, sequentially
# Deletes output after each run to save disk space

cd /usr/cpu2017 && . ./shrc

BENCHMARKS="508.namd_r 521.wrf_r 527.cam4_r 554.roms_r"
OUTFILE="/tmp/overhead_io_timing.txt"

> "$OUTFILE"

for bm in $BENCHMARKS; do
    echo "=== Running memlog-io / $bm ==="

    runcpu --action=run --config=memlog-io.cfg --size=test --noreportable --nopower --iterations=1 "$bm" 2>&1 | tail -3

    LATEST_LOG=$(ls -t /usr/cpu2017/result/CPU2017.*.log | head -1)
    ELAPSED=$(grep "Workload elapsed time" "$LATEST_LOG" | tail -1 | sed 's/.*= \([0-9.]*\) seconds/\1/')
    ELAPSED_MS=$(echo "$ELAPSED" | awk '{printf "%d", $1 * 1000}')

    echo "MEMLOG_IO ${bm}: ${ELAPSED_MS}ms" | tee -a "$OUTFILE"

    # Show output size before deleting
    LOGDIR=$(ls -td /tmp/valgrind-logs.*/  2>/dev/null | head -1)
    if [ -n "$LOGDIR" ]; then
        echo "  Output size: $(du -sh "$LOGDIR" 2>/dev/null | cut -f1)"
        rm -rf /tmp/valgrind-logs.*
        echo "  Cleaned up."
    fi
done

echo ""
echo "=== MEMLOG I/O RESULTS ==="
cat "$OUTFILE"
