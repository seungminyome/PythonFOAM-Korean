#!/bin/bash
#SBATCH --job-name=pub-unit-merged
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:40:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/publish
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/publish/slurm/unit-merged-%j.out
# COMMIT: the commit to test, from a fresh clone. The unit tests on the two CI Pythons: the module list of
# .github/workflows/tests.yml, then `make test`, and the list against the test_*.py files.
set -uo pipefail
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030
C=$W/publish/clone-${SLURM_JOB_ID}
git clone -q --no-hardlinks "$G/PythonFOAM" "$C"; git -C "$C" checkout -q "$COMMIT"
git -C "$C" rev-parse HEAD; hostname
cd "$C"
yml=$(sed -n 's/^ *run: python -m unittest //p' .github/workflows/tests.yml | sed 's/ -v$//')
mk=$(sed -n 's/.*-m unittest //p' Makefile | sed 's/ -v$//')
files=$(cd Solver_Examples/PODFoam/llm_demo && ls test_*.py | sed 's/\.py$//' | sort | tr '\n' ' ')
echo "tests.yml: $yml"; echo "Makefile:  $mk"; echo "files:     $files"
[[ "$(echo $yml | tr ' ' '\n' | sort | tr '\n' ' ')" == "$files" ]] && echo "tests.yml lists every test file" || echo "tests.yml DIFFERS from the files"
[[ "$yml" == "$mk" ]] && echo "Makefile equals tests.yml" || echo "Makefile DIFFERS from tests.yml"
export TMPDIR=${SLURM_TMPDIR:-/tmp} PYTHONDONTWRITEBYTECODE=1
for py in ci-py310 ci-py312; do
    p=/gscratch/syome/conda/$py/bin/python3
    echo "== $py $($p --version) (module list of tests.yml)"; log=$(mktemp "$TMPDIR/unit.XXXXXX")
    (cd Solver_Examples/PODFoam/llm_demo && $p -m unittest $yml -v) > "$log" 2>&1
    echo "exit $?"; grep -E '^(Ran |OK|FAILED|ERROR:|FAIL:)|skipped' "$log" | cut -c1-160; rm -f "$log"
    echo "== $py make test"; log=$(mktemp "$TMPDIR/unit.XXXXXX")
    make test PY=$p > "$log" 2>&1
    echo "exit $?"; grep -E '^(Ran |OK|FAILED|ERROR:|FAIL:)|skipped' "$log" | cut -c1-160; rm -f "$log"
done
git -C "$C" status --short | head; cd "$W/publish"; rm -rf "$C"
