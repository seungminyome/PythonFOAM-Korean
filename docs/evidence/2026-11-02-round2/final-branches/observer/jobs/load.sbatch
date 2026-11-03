#!/bin/bash
#SBATCH --job-name=r4o-load
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G
#SBATCH --time=02:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer/logs/load-%j.out
# env: PY (python), N (runs), PAR (parallel copies), SRCDIR (export under src/: load-py310 or load-py312, both
# r4/pr-observer 24e9df6). First the three unit-test modules once, unloaded; then the whole test_async module N
# times, PAR copies in parallel (tools/run_one.sh). Pattern: r3/assemble/jobs/load2.sbatch.
set -uo pipefail
R=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer
SRC=$R/src/$SRCDIR/Solver_Examples/PODFoam/llm_demo; OUT=$R/load/$SRCDIR-${PAR}x${N}-$SLURM_JOB_ID; mkdir -p "$OUT"
echo "host $(hostname) cpus=$SLURM_CPUS_PER_TASK nproc=$(nproc) py=$PY N=$N PAR=$PAR HEAD=$(cat $R/src/$SRCDIR/HEAD) start $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)" | tee "$OUT/job.txt"
"$PY" -c 'import sys, numpy, matplotlib, scipy; print(sys.version.split()[0], numpy.__version__, matplotlib.__version__, scipy.__version__)' | tee -a "$OUT/job.txt"
( cd "$SRC" && "$PY" -B -m unittest test_llm_client test_callback test_async > "$OUT/unittest-unloaded.log" 2>&1; echo "unloaded unit tests rc=$? $(grep -E '^Ran ' $OUT/unittest-unloaded.log) $(tail -1 $OUT/unittest-unloaded.log)" ) | tee -a "$OUT/job.txt"
for m in test_llm_client test_callback test_async; do ( cd "$SRC" && "$PY" -B -m unittest $m 2>&1 | grep -E '^Ran ' | sed "s/^/$m: /" ); done | tee -a "$OUT/job.txt"
seq 1 "$N" | xargs -P "$PAR" -I{} "$R/tools/run_one.sh" "$PY" "$SRC" "$OUT" {}
echo "end $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)" | tee -a "$OUT/job.txt"
pass=$(grep -c ' rc=0 ' "$OUT/summary.txt"); echo "passed $pass of $N" | tee -a "$OUT/job.txt"
grep -h -E '^(FAIL|ERROR): ' "$OUT"/run-*.log | sort | uniq -c | tee -a "$OUT/job.txt"
grep -h -E '^AssertionError' "$OUT"/run-*.log | cut -c1-120 | sort | uniq -c | tee -a "$OUT/job.txt"
echo "walls: $(awk '{sub("wall=","",$4); print $4}' $OUT/summary.txt | sort -n | sed -n '1p;$p' | tr '\n' ' ')" | tee -a "$OUT/job.txt"
echo "loads: $(awk '{sub("load=","",$5); print $5}' $OUT/summary.txt | sort -n | sed -n '1p;$p' | tr '\n' ' ')" | tee -a "$OUT/job.txt"
echo "files newer than HEAD in the export: $(cd $R/src/$SRCDIR && find . -newer HEAD -type f | wc -l)" | tee -a "$OUT/job.txt"
