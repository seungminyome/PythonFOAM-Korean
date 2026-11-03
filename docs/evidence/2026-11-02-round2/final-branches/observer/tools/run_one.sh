#!/bin/bash
# usage: run_one.sh <python> <llm_demo dir> <out dir> <k> ; runs the whole test_async module once
PY=$1; SRC=$2; OUT=$3; K=$4
cd "$SRC" || exit 2
start=$(date +%s.%N)
"$PY" -B -m unittest test_async > "$OUT/run-$K.log" 2>&1; rc=$?
end=$(date +%s.%N)
printf "run %s rc=%s wall=%.1f load=%s %s\n" "$K" "$rc" "$(echo "$end - $start" | bc)" "$(cut -d' ' -f1 /proc/loadavg)" "$(grep -E '^Ran ' "$OUT/run-$K.log" | head -1)" >> "$OUT/summary.txt"
exit 0
