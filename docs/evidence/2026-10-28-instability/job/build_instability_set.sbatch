#!/bin/bash
#SBATCH --job-name=build-instability-set
#SBATCH --account=me5475
#SBATCH --partition=mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/picture-test-20261021/build-instability-set-%j.out
# Build the instability test set of 2026-10-28 (instability_test.py build) from the design in
# docs/evidence/2026-10-28-instability/test-set/design.json, then check it. No model, no GPU.
set -euo pipefail
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-inst
OUT=/cluster/medbow/gscratch/syome/github_repos/picture-test-20261021/instability-test-20261028
export PATH=/gscratch/syome/conda/s4f/bin:$PATH MPLCONFIGDIR=$TMPDIR/mpl OPENBLAS_NUM_THREADS=1
git -C "$REPO" rev-parse HEAD; git -C "$REPO" status --short
cd "$REPO/Solver_Examples/PODFoam/llm_demo"
python3 instability_test.py build --design "$REPO/docs/evidence/2026-10-28-instability/test-set/design.json" \
    --centres "$REPO/docs/evidence/2026-10-20/pod-llm-async.pp7agC/async-no-llm/llm_observation/step-000250/fields.npz" \
    --output "$OUT"
python3 instability_test.py check --test-set "$OUT"
du -sh "$OUT"
