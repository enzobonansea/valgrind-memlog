#!/bin/bash
# Run one benchmark without rounding and list the allocating statement of every tracked block.
# Usage: list_sites.sh <benchmark>
BM=$1
cd /usr/cpu2017 && . ./shrc
runcpu --action=run --config=memlog-mx.cfg --define label=wl --define mbits=52 --define emin=-1000 \
    --define listsites=yes --define sites=/work/sites/none.txt \
    --size=test --noreportable --nopower --iterations=1 "$BM" > /work/out/"$BM"_listsites.runcpu 2>&1
grep -h MXSITE /tmp/mx_wl_52_*.log > /work/out/"$BM"_sites_listed.txt
rm -f /tmp/mx_wl_52_*.log
grep -E "Success|elapsed" "$(ls -t /usr/cpu2017/result/CPU2017.*.log | head -1)" | tail -2
