#!/bin/bash
#SBATCH --job-name=r4f-slice3d
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/slice3d
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/logs/slice3d-%x-%j.out
# One no-model 3D slice run at the r4/pr-observer tip (src/obs). Environment: VER (v2212, 8).
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; F=$W/r4/fix
case $VER in
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown $VER"; exit 2;;
esac
RUN=$F/slice3d/$VER-$SLURM_JOB_ID; mkdir -p $RUN/src
cp $F/src/obs/HEAD $RUN/HEAD; cp -a $F/src/obs/Solver_Examples $RUN/src/
echo "job $SLURM_JOB_ID node $(hostname) code $(cat $RUN/HEAD) start $(date -u +%FT%TZ)"
module load apptainer
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash $F/jobs/slice3d_inner.sh "$RUN" "$RUN/src" "$VER" "$RC"
echo "inner exit $? end $(date -u +%FT%TZ)"
