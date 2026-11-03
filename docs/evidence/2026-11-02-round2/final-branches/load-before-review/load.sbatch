#!/bin/bash
#SBATCH --job-name=r3a-load
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G
#SBATCH --time=02:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r3/assemble
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r3/assemble/logs/load-%j.out
# env: PY (python), N (runs), PAR (parallel copies). First the three unit-test modules once, unloaded; then the whole
# test_async module N times, PAR copies in parallel (load/run_one.sh from the phase-1 observer stream).
set -uo pipefail
A=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r3/assemble
SRC=$A/src/obs/Solver_Examples/PODFoam/llm_demo; OUT=$A/load/$(basename $(dirname $PY))-${PAR}x${N}-$SLURM_JOB_ID; mkdir -p "$OUT"
echo "host $(hostname) cpus=$SLURM_CPUS_PER_TASK nproc=$(nproc) py=$PY N=$N PAR=$PAR HEAD=$(cat $A/src/obs/HEAD) start $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)" | tee "$OUT/job.txt"
"$PY" -c 'import sys, numpy, matplotlib, scipy; print(sys.version.split()[0], numpy.__version__, matplotlib.__version__, scipy.__version__)' | tee -a "$OUT/job.txt"
( cd "$SRC" && "$PY" -B -m unittest test_llm_client test_callback test_async > "$OUT/unittest-unloaded.log" 2>&1; echo "unloaded unit tests rc=$? $(grep -E '^Ran ' $OUT/unittest-unloaded.log) $(tail -1 $OUT/unittest-unloaded.log)" ) | tee -a "$OUT/job.txt"
for m in test_llm_client test_callback test_async; do ( cd "$SRC" && "$PY" -B -m unittest $m 2>&1 | grep -E '^Ran ' | sed "s/^/$m: /" ); done | tee -a "$OUT/job.txt"
seq 1 "$N" | xargs -P "$PAR" -I{} "$A/load/run_one.sh" "$PY" "$SRC" "$OUT" {}
echo "end $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)" | tee -a "$OUT/job.txt"
pass=$(grep -c ' rc=0 ' "$OUT/summary.txt"); echo "passed $pass of $N" | tee -a "$OUT/job.txt"
grep -h -E '^(FAIL|ERROR): ' "$OUT"/run-*.log | sort | uniq -c | tee -a "$OUT/job.txt"
grep -h -E '^AssertionError' "$OUT"/run-*.log | cut -c1-120 | sort | uniq -c | tee -a "$OUT/job.txt"
echo "walls: $(awk '{sub("wall=","",$4); print $4}' $OUT/summary.txt | sort -n | sed -n '1p;$p' | tr '\n' ' ')"
echo "untracked files left in the export: $(cd $A/src/obs && git -C /cluster/medbow/gscratch/syome/github_repos/PythonFOAM --work-tree=$A/src/obs status --short 2>/dev/null | grep -v '^ D\|validation/runs' | wc -l)"
