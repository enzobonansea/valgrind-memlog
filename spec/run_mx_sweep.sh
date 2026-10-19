#!/bin/bash
# Sweep MX element mantissa widths on one benchmark and record SPEC's own
# validation verdict. "off" runs Memlog without rounding as the control.
# Usage: run_mx_sweep.sh <benchmark> <sites file> [mbits|off ...]
set -u
BM=${1:-554.roms_r}
SITES=${2:-/work/sites.txt}
shift 2 || true
MBITS=${*:-"off 52 23 16 10 7 3"}
EMIN=${EMIN:--6}
mkdir -p /work/out
OUT=/work/out/mx_results_${BM}.txt

cd /usr/cpu2017 && . ./shrc

for m in $MBITS; do
    echo "=== $BM mbits=$m emin=$EMIN sites=$SITES ===" | tee -a "$OUT"
    if [ "$m" = off ]; then
        CFG=(--config=memlog-noop.cfg)
    else
        CFG=(--config=memlog-mx.cfg --define mbits="$m" --define emin="$EMIN" --define sites="$SITES")
    fi
    runcpu --action=run "${CFG[@]}" --size=test --noreportable --nopower \
        --iterations=1 "$BM" > /work/out/runcpu_${BM}_$m.txt 2>&1
    LOG=$(ls -t /usr/cpu2017/result/CPU2017.*.log | head -1)
    cp "$LOG" /work/out/
    grep -E "Workload elapsed time|Success|miscompare|errors" "$LOG" | tail -4 | tee -a "$OUT"
    grep -h "MX:" /tmp/mx_mytest_"$m"_*.log 2>/dev/null | tail -3 | tee -a "$OUT"
    rm -f /tmp/mx_mytest_"$m"_*.log
    RUNDIR=$(ls -td /usr/cpu2017/benchspec/CPU/"$BM"/run/run_base_test_* | head -1)
    for f in "$RUNDIR"/*.log "$RUNDIR"/*.out; do
        [ -f "$f" ] && cp "$f" /work/out/"$(basename "$f").m${m}_e${EMIN}"
    done
    for f in "$RUNDIR"/*.mis; do
        [ -f "$f" ] && { echo "--- $(basename "$f")"; head -25 "$f"; } | tee -a "$OUT"
    done
done
