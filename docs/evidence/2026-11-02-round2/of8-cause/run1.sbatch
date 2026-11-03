#!/bin/bash
#SBATCH --job-name=of8-cause
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=00:20:00
# Environment: VER (8 | v2212), DIM (2d | 3d), VARIANTS (space-separated letters of dicts/fvSolution.*)
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
R=$W/r2/of8-cause
case $VER in
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown VER $VER"; exit 2;;
esac
OUT=$R/runs1/$VER-$DIM-$SLURM_JOB_ID; mkdir -p "$OUT"
echo "$VARIANTS" > "$OUT/variants.txt"
hostname > "$OUT/node.txt"; sha256sum "$SIF" > "$OUT/image-sha256.txt"
module load apptainer
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$R/inner1.sh" "$OUT" "$VER" "$RC" "$DIM"
echo "inner exit $?"
