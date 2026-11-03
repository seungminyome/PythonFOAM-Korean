#!/bin/bash
#SBATCH --job-name=r4f-unit
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/logs/unit-%j.out
# The three unit-test modules of llm_demo, unloaded, on the export of the r4/pr-observer tip (src/obs), with
# ci-py310 and ci-py312 one after the other (no copies in parallel).
set -uo pipefail
A=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix; SRC=$A/src/obs/Solver_Examples/PODFoam/llm_demo
echo "host $(hostname) nproc=$(nproc) HEAD=$(cat $A/src/obs/HEAD) start $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)"
for env in ci-py310 ci-py312; do
  PY=/gscratch/syome/conda/$env/bin/python3; LOG=$A/logs/unit-$env-$SLURM_JOB_ID.log
  "$PY" -c 'import sys, numpy, matplotlib, scipy; print(sys.version.split()[0], numpy.__version__, matplotlib.__version__, scipy.__version__)'
  ( cd "$SRC" && "$PY" -B -m unittest test_llm_client test_callback test_async > "$LOG" 2>&1 ); rc=$?
  echo "$env rc=$rc $(grep -E '^Ran ' $LOG) $(tail -1 $LOG)"
done
echo "end $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)"
