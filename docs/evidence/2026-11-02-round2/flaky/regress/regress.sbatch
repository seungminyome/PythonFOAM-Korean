#!/bin/bash
#SBATCH --job-name=flaky-regress
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G
#SBATCH --time=01:00:00
# env: PY, SRC (llm_demo dir of the worktree), OUT, LOADSRC (same), R (this folder)
mkdir -p "$OUT"; cd "$SRC" || exit 2
echo "host $(hostname) cpus=$SLURM_CPUS_PER_TASK py=$PY src=$SRC start $(date) load=$(cut -d' ' -f1 /proc/loadavg)" | tee "$OUT/job.txt"
"$PY" -c 'import sys, scipy, matplotlib, numpy; print(sys.version); print("scipy", scipy.__version__, "mpl", matplotlib.__version__, "numpy", numpy.__version__)' | tee -a "$OUT/job.txt"
# 1. unloaded: the three modules once each
for m in test_llm_client test_callback test_async; do
  s=$(date +%s.%N); "$PY" -B -m unittest "$m" > "$OUT/$m.log" 2>&1; rc=$?; e=$(date +%s.%N)
  printf "%s rc=%s wall=%.1f %s\n" "$m" "$rc" "$(echo "$e - $s" | bc)" "$(grep -E '^(Ran|OK|FAILED)' "$OUT/$m.log" | tr '\n' ' ')" | tee -a "$OUT/job.txt"
done
# 2. loaded margin probe: 8 copies of the whole module as load, 50 probes of the fixed scenario (8 parallel) on top
mkdir -p "$OUT/loadgen"
( seq 1 8 | xargs -P 8 -I{} sh -c "cd '$SRC' && '$PY' -B -m unittest test_async > '$OUT/loadgen/run-{}.log' 2>&1" ) &
LG=$!
sleep 20   # let the load build up
seq 1 50 | xargs -P 8 -I{} sh -c "cd '$SRC' && '$PY' -B -I -u '$R/probe_refused30.py' '$SRC' >> '$OUT/probes.jsonl' 2>>'$OUT/probes.err'"
echo "probes done $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)" | tee -a "$OUT/job.txt"
wait $LG
echo "loadgen done $(date)" | tee -a "$OUT/job.txt"
grep -h -E '^(Ran|OK|FAILED)' "$OUT"/loadgen/run-*.log | sort | uniq -c | tee -a "$OUT/job.txt"
"$PY" - "$OUT/probes.jsonl" <<'PYEOF' | tee -a "$OUT/job.txt"
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
print("probes", len(rows), "status", sorted(set(r["status"] for r in rows)), "phase", sorted(set(str(r["phase"]) for r in rows)),
      "sent", sorted(set(str(r["sent"]) for r in rows)), "reaped", sorted(set(str(r["reaped"]) for r in rows)))
for k in ("inference_wall_s", "max_wall_lt10", "wall10", "render_s", "callback_elapsed_s", "arrived_at_step"):
    v = [r[k] for r in rows]; print(k, "min", min(v), "median", sorted(v)[len(v)//2], "max", max(v))
print("load min/max", min(float(r["load"]) for r in rows), max(float(r["load"]) for r in rows))
PYEOF
echo "end $(date)" | tee -a "$OUT/job.txt"
