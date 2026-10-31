#!/bin/bash
#SBATCH --job-name=pod-version-check
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/slurm/version-check-%x-%j.out
# One OpenFOAM version: build and bridge validation (validation/run_v2106.sh), then the observer in
# solver runs with no model (LLM_ENABLED=0): the 2D step case and the 3D slice case, serial and on 2 ranks.
# Environment: VER (v2012, v2106, v2212, 8), REPO (checkout to test), OUT_ROOT (default: pod-versions-20261030/matrix-runs)
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
REPO=${REPO:-/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-compat}
OUT_ROOT=${OUT_ROOT:-$W/matrix-runs}
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown VER $VER"; exit 2;;
esac
OUT=$OUT_ROOT/$VER-${SLURM_JOB_ID:-local}; mkdir -p "$OUT"
module load apptainer
git -C "$REPO" rev-parse HEAD > "$OUT/HEAD"; git -C "$REPO" status --short > "$OUT/git-status.txt"
sha256sum "$SIF" > "$OUT/image-sha256.txt"
hostname > "$OUT/node.txt"
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$W/matrix/version_check_inner.sh" "$OUT" "$REPO" "$VER" "$RC"
echo "inner exit $?"
