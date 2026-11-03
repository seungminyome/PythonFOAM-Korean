#!/bin/bash
#SBATCH --job-name=r4o-unit
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer/logs/unit-%j.out
# The three llm_demo unit-test modules, unloaded (one Python after the other), on the export of r4/pr-observer
# (src/unit), verbose so every test name and result is in the log. Pattern: r3/assemble/jobs/unit_opus.sbatch.
set -uo pipefail
R=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer; SRC=$R/src/unit/Solver_Examples/PODFoam/llm_demo
echo "host $(hostname) nproc=$(nproc) HEAD=$(cat $R/src/unit/HEAD) start $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)"
echo "FOAM vars: $(env | grep -c -E '^(WM_|FOAM_)') llama-server on PATH: $(command -v llama-server || echo none)"
for env in ci-py310 ci-py312; do
  PY=/gscratch/syome/conda/$env/bin/python3; LOG=$R/logs/unit-$env-$SLURM_JOB_ID.log
  "$PY" -c 'import sys, numpy, matplotlib, scipy; print(sys.version.split()[0], numpy.__version__, matplotlib.__version__, scipy.__version__)'
  ( cd "$SRC" && "$PY" -B -m unittest -v test_llm_client test_callback test_async > "$LOG" 2>&1 ); rc=$?
  echo "$env rc=$rc $(grep -E '^Ran ' $LOG) $(tail -1 $LOG)"
  for m in test_llm_client test_callback test_async; do echo "  $m: $(grep -c -E "\($m\.[A-Za-z_]+\.test_[A-Za-z0-9_]+\) \.\.\. ok$|^test_[A-Za-z0-9_]+ \($m\.[A-Za-z_]+\.test_[A-Za-z0-9_]+\)" $LOG) lines"; done
  grep -E 'restart|mismatch' "$LOG"
done
echo "end $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)"
echo "files newer than HEAD in the export: $(cd $R/src/unit && find . -newer HEAD -type f | wc -l)"
