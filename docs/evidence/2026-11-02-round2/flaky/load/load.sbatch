#!/bin/bash
#SBATCH --job-name=flaky-load
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --nodes=1 --ntasks=1
#SBATCH --time=02:00:00
# env: PY (python), SRC (llm_demo dir), OUT (out dir), N (runs), PAR (parallel copies)
mkdir -p "$OUT"
echo "host $(hostname) cpus=$SLURM_CPUS_PER_TASK nproc=$(nproc) py=$PY src=$SRC N=$N PAR=$PAR start $(date)" | tee "$OUT/job.txt"
"$PY" -c 'import sys; print(sys.version)' | tee -a "$OUT/job.txt"
seq 1 "$N" | xargs -P "$PAR" -I{} "$SLURM_SUBMIT_DIR/run_one.sh" "$PY" "$SRC" "$OUT" {}
echo "end $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)" | tee -a "$OUT/job.txt"
pass=$(grep -c ' rc=0 ' "$OUT/summary.txt"); echo "passed $pass of $N" | tee -a "$OUT/job.txt"
grep -h -E '^(FAIL|ERROR): ' "$OUT"/run-*.log | sort | uniq -c | tee -a "$OUT/job.txt"
grep -h -E '^AssertionError' "$OUT"/run-*.log | cut -c1-120 | sort | uniq -c | tee -a "$OUT/job.txt"
