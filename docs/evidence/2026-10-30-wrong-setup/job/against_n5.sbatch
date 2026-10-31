#!/bin/bash
#SBATCH --job-name=wrong-setup-n5
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/against-n5-%j.out
# flow/against_n5.py of the evidence folder.
set -euo pipefail
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
EV=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup/docs/evidence/2026-10-30-wrong-setup
hostname
OPENBLAS_NUM_THREADS=1 /gscratch/syome/conda/s4f/bin/python3 "$EV/flow/against_n5.py" "$HERE/wrong-setup-test-20261030" "$EV/flow/against-n5.json"
