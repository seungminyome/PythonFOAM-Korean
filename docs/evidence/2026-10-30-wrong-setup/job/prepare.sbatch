#!/bin/bash
#SBATCH --job-name=wrong-setup-prepare
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261030/jobs/prepare-%j.out
# The ten cases of the wrong-setup test (wrong_setup_test.py prepare) from the developed flow of
# 2026-10-22; no solver runs here.
set -euo pipefail
export PATH=/gscratch/syome/conda/s4f/bin:$PATH OPENBLAS_NUM_THREADS=1
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup
hostname; git -C "$REPO" rev-parse HEAD; git -C "$REPO" status --short
cd "$REPO/Solver_Examples/PODFoam/llm_demo"
sha256sum wrong_setup_test.py
python3 wrong_setup_test.py prepare --long /cluster/medbow/gscratch/syome/github_repos/flow-states-20261022/long-100ms \
    --output /cluster/medbow/gscratch/syome/github_repos/flow-states-20261030
