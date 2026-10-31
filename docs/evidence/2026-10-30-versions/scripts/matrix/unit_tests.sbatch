#!/bin/bash
#SBATCH --job-name=pod-unit-tests
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:40:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/slurm/unit-tests-%x-%j.out
# REPO's unit tests on the two CI Pythons, one after the other. MODULES: the modules to run (default: all test_*.py in llm_demo).
set -uo pipefail
cd "$REPO/Solver_Examples/PODFoam/llm_demo"
git -C "$REPO" rev-parse HEAD 2>/dev/null
MODULES=${MODULES:-$(ls test_*.py | sed 's/\.py$//' | tr '\n' ' ')}
echo "modules: $MODULES"; hostname
export TMPDIR=${SLURM_TMPDIR:-/tmp}
for py in ci-py310 ci-py312; do
    echo "== $py"; log=$(mktemp "$TMPDIR/unit.XXXXXX"); PYTHONDONTWRITEBYTECODE=1 /gscratch/syome/conda/$py/bin/python -m unittest $MODULES > "$log" 2>&1
    echo "exit $?"; grep -E '^(Ran |OK|FAILED|ERROR:|FAIL:)' "$log"; rm -f "$log"
done
