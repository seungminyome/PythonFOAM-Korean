#!/bin/bash
#SBATCH --job-name=pod-3d-slice
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:30:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/slice-test-%j.out
# v2 observer pictures of a 3D case through a plane slice (2026-10-28). Builds PODFoam from the
# observer-3d worktree and runs the 2D bridge validation, makes the 3D step case (8 cells in z,
# walls front and back, the developed 2D flow at t = 0.1 s in every layer), runs it with the
# observer (v2 frame at step 100, no model) serially and on 2 ranks, without the observer, with
# LLM_SLICE_Z set, with two refused LLM_SLICE_Z values, and runs the 2D case with the new build;
# then compare_3d.py writes frame-comparison.json. Everything runs inside slice_test_inner.sh.
set -euo pipefail
module load apptainer
OUT=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-$SLURM_JOB_ID
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-3d
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
REF2D=/cluster/medbow/gscratch/syome/github_repos/pod-mpi-20261027/run-24903786/serial/llm_observation/step-000100
EVID=$REPO/docs/evidence/2026-10-28-3d
mkdir -p "$OUT"
git -C "$REPO" rev-parse HEAD > "$OUT/HEAD"; git -C "$REPO" status --short > "$OUT/git-status.txt"; git -C "$REPO" diff > "$OUT/changes.patch"
echo "node $(hostname) start $(date -Is)"
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif \
    bash "$EVID/slice_test_inner.sh" "$OUT" "$REPO" "$SRC"
/gscratch/syome/conda/s4f/bin/python3 "$EVID/compare_3d.py" "$OUT" "$REF2D"
# the POD module's audit files (snapshots of 50 steps, about 200 MB each) are not needed
rm -f "$OUT"/*/python_svd_audit.npz
echo "end $(date -Is)"
