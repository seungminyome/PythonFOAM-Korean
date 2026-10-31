#!/bin/bash
#SBATCH --job-name=wrong-setup-facts
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/frame-facts-%j.out
# flow/frame_facts.py of the evidence folder: what the frames, the mesh and the pictures hold.
set -euo pipefail
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup
EV=$REPO/docs/evidence/2026-10-30-wrong-setup
hostname
export OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=${SLURM_TMPDIR:-/tmp}/mpl-$$
/gscratch/syome/conda/s4f/bin/python3 "$EV/flow/frame_facts.py" "$HERE/wrong-setup-test-20261030" \
    /cluster/medbow/gscratch/syome/github_repos/flow-states-20261030/N1/constant/polyMesh \
    "$REPO/Solver_Examples/PODFoam/llm_demo" "$EV/flow/frame-facts.json"
