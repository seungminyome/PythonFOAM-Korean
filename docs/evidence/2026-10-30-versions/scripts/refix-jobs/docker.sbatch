#!/bin/bash
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
# Environment: REPO
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; R=$W/pr/refix
OUT=$R/docker-$SLURM_JOB_ID; mkdir -p $OUT/PF
git -C $REPO archive HEAD | tar -x -C $OUT/PF; git -C $REPO rev-parse HEAD
module load apptainer
apptainer exec --bind /cluster/medbow/gscratch $W/pr/maint-review/images/upstream-docker.sif bash $R/jobs/docker_inner.sh $OUT
echo "inner exit $?"
