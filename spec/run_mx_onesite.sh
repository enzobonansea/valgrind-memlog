#!/bin/bash
# Round one allocation site at a time ("site mbits" lines in the jobs file).
# Each parallel worker uses its own SPEC label so run directories do not collide.
# Usage: run_mx_onesite.sh <benchmark> <jobs file> [workers] [emin]
set -u
BM=$1
JOBS=$2
WORKERS=${3:-6}
EMIN=${4:--1000}
OUT=${OUTDIR:-/work/out/onesite}
mkdir -p "$OUT"

cd /usr/cpu2017 && . ./shrc

worker() {
    local w=$1 label="${LABEL_PREFIX:-w}$1" n=0
    while read -r site m; do
        n=$((n + 1))
        [ $(( (n - 1) % WORKERS )) -eq "$w" ] || continue
        local tag="$(basename "$site" .txt).m${m}.e${EMIN}"
        [ -f "$OUT/$tag.done" ] && continue
        local sf="/tmp/site_${label}.txt"
        if [ -f "$site" ]; then cp "$site" "$sf"; else echo "$site" > "$sf"; fi
        runcpu --action=run --config=memlog-mx.cfg --define label="$label" --define esz="${ESZ:-8}" --define listsites="${LISTSITES:-no}" \
            --define mbits="$m" --define emin="$EMIN" --define sites="$sf" \
            --size=test --noreportable --nopower --iterations=1 "$BM" \
            > "$OUT/$tag.runcpu" 2>&1
        local rundir
        rundir=$(ls -td /usr/cpu2017/benchspec/CPU/"$BM"/run/run_base_test_"$label"-m64.* | head -1)
        cp "$rundir"/ocean_benchmark0.log "$OUT/$tag.log" 2>/dev/null
        cp "$rundir"/diffwrf_output_01.txt "$OUT/$tag.diffwrf" 2>/dev/null
        cat "$rundir"/*.mis > "$OUT/$tag.mis" 2>/dev/null
        grep -h "MX:\|MXSITE" /tmp/mx_"$label"_"$m"_*.log 2>/dev/null > "$OUT/$tag.mx"
        rm -f /tmp/mx_"$label"_"$m"_*.log
        touch "$OUT/$tag.done"
    done < "$JOBS"
}

for w in $(seq 0 $((WORKERS - 1))); do
    worker "$w" &
done
wait
