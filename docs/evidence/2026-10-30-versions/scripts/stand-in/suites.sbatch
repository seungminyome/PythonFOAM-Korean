#!/bin/bash
#SBATCH --job-name=pr-stub-suites
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/slurm/pr-stub-suites-%x-%j.out
# run_demo.sh, both suites, in one version's image, against a stand-in server with no model. Environment: VER, REPO.
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown VER $VER"; exit 2;;
esac
OUT=$W/pr/stub-runs/$VER-${SLURM_JOB_ID:-local}; mkdir -p "$OUT/git"
export OUT REPO VER RC
module load apptainer
git -C "$REPO" rev-parse HEAD | tee "$OUT/git/HEAD"; git -C "$REPO" status --short > "$OUT/git/git-status.txt"; git -C "$REPO" diff --binary > "$OUT/git/changes.patch"
hostname
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$W/pr/stub/suites_inner.sh"
echo "inner exit $?"
