#!/bin/bash
#SBATCH --job-name=inst2-build
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/instability
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/instability/logs/build-%j.out
# Build the three sets of the 2026-11-01 instability test (instability_test2.py build), then check.
set -euo pipefail
R=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/instability
REPO=$R/wt
OUT=$R/test-set
export PATH=/gscratch/syome/conda/s4f/bin:$PATH MPLCONFIGDIR=${TMPDIR:-/tmp}/mpl-$SLURM_JOB_ID OPENBLAS_NUM_THREADS=1
hostname; date -u +%FT%TZ
git -C "$REPO" rev-parse HEAD; git -C "$REPO" status --short
cd "$REPO/Solver_Examples/PODFoam/llm_demo"
python3 instability_test2.py build --design "$R/design2.json" \
    --centres "$REPO/docs/evidence/2026-10-20/pod-llm-async.pp7agC/async-no-llm/llm_observation/step-000250/fields.npz" \
    --oct28-manifest "$REPO/docs/evidence/2026-10-28-instability/test-set/manifest.json" \
    --output "$OUT"
python3 instability_test2.py check --test-set "$OUT"
du -sh "$OUT"; ls "$OUT/frames" | head; find "$OUT/frames" -name U.png | wc -l
date -u +%FT%TZ
