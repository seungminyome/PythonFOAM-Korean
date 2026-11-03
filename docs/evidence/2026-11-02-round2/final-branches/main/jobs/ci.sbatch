#!/bin/bash
#SBATCH --job-name=r4i-ci
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --nodes=1 --ntasks=1 --cpus-per-task=4 --mem=16G
#SBATCH --time=00:45:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/integrate
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/integrate/logs/ci-%j.out
# The CI unit-test list (the modules named in .github/workflows/tests.yml of the export) on ci-py310 and
# ci-py312, one after the other, unloaded. Usage: sbatch ci.sbatch <export dir with HEAD file>
set -uo pipefail
SRC=${1:?export dir}; LLM=$SRC/Solver_Examples/PODFoam/llm_demo
MODS=$(grep -oE 'python -m unittest [a-z_0-9 ]+' $SRC/.github/workflows/tests.yml | head -1 | sed 's/python -m unittest //')
echo "host $(hostname) nproc=$(nproc) export=$SRC HEAD=$(cat $SRC/HEAD) start $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)"
echo "FOAM vars: $(env | grep -c -E '^(WM_|FOAM_)') llama-server on PATH: $(command -v llama-server || echo none)"
echo "modules: $MODS"
for env in ci-py310 ci-py312; do
  PY=/gscratch/syome/conda/$env/bin/python3; LOG=logs/ci-$env-$SLURM_JOB_ID.log
  echo "$env: $("$PY" -c 'import sys, numpy, scipy, matplotlib; print(sys.version.split()[0], "numpy", numpy.__version__, "scipy", scipy.__version__, "matplotlib", matplotlib.__version__)')"
  ( cd "$LLM" && env -u PYTHONPATH PYTHONNOUSERSITE=1 MPLBACKEND=Agg "$PY" -B -m unittest -v $MODS > "$OLDPWD/$LOG" 2>&1 ); rc=$?
  echo "$env rc=$rc $(grep -E '^Ran ' $LOG) $(tail -1 $LOG)"
  for m in $MODS; do echo "  $m: $(grep -oE "^test_[A-Za-z0-9_]+ \($m\.[A-Za-z0-9_]+" $LOG | sort -u | wc -l) tests"; done
  grep -E '^(ERROR|FAIL):' $LOG | head -40
done
echo "end $(date) load=$(cut -d' ' -f1-3 /proc/loadavg)"
echo "files newer than HEAD in the export: $(cd $SRC && find . -newer HEAD -type f -not -path '*/__pycache__/*' | wc -l)"
