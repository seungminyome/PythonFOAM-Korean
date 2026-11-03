#!/bin/bash
#SBATCH --job-name=r4f-smoke
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/smoke
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/logs/smoke-%x-%j.out
# Hooks smoke test at the r4/pr-observer tip (src/obs), with phase 3's inner script, hooks_tail.py and one-patch
# case (r3/solver/smoke, read only). Environment: VER (8, v2106).
#  A: shipped Run_Case + validation module + hooks, podSvdInterval 3, endTime 1e-4, 0/uniform/time removed
#  B: a module holding only the two hooks (must stop: snapshot_func and svd_func required)
#  C: small 2D channel with ONE empty patch (frontAndBack): one polygon per cell
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; F=$W/r4/fix; SM=$W/r3/solver/smoke
case $VER in
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown $VER"; exit 2;;
esac
OUT=$F/smoke/$VER-$SLURM_JOB_ID; mkdir -p $OUT/src
cp $F/src/obs/HEAD $OUT/HEAD; echo "job $SLURM_JOB_ID node $(hostname) code $(cat $OUT/HEAD)"
cp -a $F/src/obs/Solver_Examples $OUT/src/
module load apptainer
export OUT RC VER SM
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash $SM/smoke_inner.sh
echo "inner exit $?"
