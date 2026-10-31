#!/bin/bash
#SBATCH --job-name=wrong-setup-build
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/build-set-%j.out
# Check the ten runs' logs and setups, then build and check the wrong-setup test set
# (wrong_setup_test.py flow-check, build, check, contact). No model, no GPU.
set -euo pipefail
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup
FLOW=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261030
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
OUT=$HERE/wrong-setup-test-20261030
export PATH=/gscratch/syome/conda/s4f/bin:$PATH MPLCONFIGDIR=${TMPDIR:-/tmp}/mpl-$SLURM_JOB_ID OPENBLAS_NUM_THREADS=1
hostname; git -C "$REPO" rev-parse HEAD; git -C "$REPO" status --short
cd "$REPO/Solver_Examples/PODFoam/llm_demo"
python3 wrong_setup_test.py flow-check --design "$FLOW/design.json" --output "$FLOW/flow-check.json" > /dev/null
python3 wrong_setup_test.py build --design "$FLOW/design.json" \
    --centres "$REPO/docs/evidence/2026-10-20/pod-llm-async.pp7agC/async-no-llm/llm_observation/step-000250/fields.npz" \
    --output "$OUT"
python3 wrong_setup_test.py check --test-set "$OUT"
python3 wrong_setup_test.py contact --test-set "$OUT" --output "$HERE/contact-sheet.png"
ls -la "$HERE/contact-sheet.png"; du -sh "$OUT"
