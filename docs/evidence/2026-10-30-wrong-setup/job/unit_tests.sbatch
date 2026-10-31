#!/bin/bash
#SBATCH --job-name=wrong-setup-tests
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup/Solver_Examples/PODFoam/llm_demo
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/unit-tests-%j.out
# TESTS: modules to run (default: the full list); the two Python versions of CI.
set -uo pipefail
export OPENBLAS_NUM_THREADS=1
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup
hostname; git -C "$REPO" rev-parse HEAD; git -C "$REPO" status --short | head -20
tests=${TESTS:-test_llm_client test_callback test_ablation_runner test_async test_picture_test test_instability_test test_wrong_setup_test}
export TMPDIR=${SLURM_TMPDIR:-/tmp}
for py in /gscratch/syome/conda/ci-py310/bin/python /gscratch/syome/conda/ci-py312/bin/python; do
    echo "== $py"; $py --version
    # the tests' own prints go to /dev/null; the runner's lines are on stderr
    MPLCONFIGDIR=$TMPDIR/mpl-$$ $py -m unittest $tests 2>&1 >/dev/null | tail -${TAIL:-25}
done
