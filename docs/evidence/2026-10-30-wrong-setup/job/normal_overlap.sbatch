#!/bin/bash
#SBATCH --job-name=wrong-setup-overlap
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/normal-overlap-%j.out
# flow/normal_overlap.py of the evidence folder: normal frames at one flow time, compared.
set -euo pipefail
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
EV=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup/docs/evidence/2026-10-30-wrong-setup
hostname
OPENBLAS_NUM_THREADS=1 /gscratch/syome/conda/s4f/bin/python3 "$EV/flow/normal_overlap.py" "$HERE/wrong-setup-test-20261030" \
    /cluster/medbow/gscratch/syome/github_repos/flow-states-20261022/long-100ms "$EV/flow/normal-overlap.json"
