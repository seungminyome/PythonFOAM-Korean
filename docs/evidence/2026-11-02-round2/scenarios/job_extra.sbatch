#!/bin/bash
#SBATCH --job-name=r2-scenx
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --exclude=t527
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/scenarios
# extra scenario sets (review-cpp scenarios2/3 minus commit1) at bf7a06e; VER in v2012 v2106 v2212 8
N=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/scenarios
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
module load apptainer
export WM_NCOMPPROCS=4
case $VER in v2012) SIF=$W/images/of-v2012-dev.sif;; v2106) SIF=$W/images/of-v2106-dev.sif;; v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif;; 8) SIF=$W/images/of-8.sif;; esac
echo "VER $VER SIF $SIF node $(hostname) job $SLURM_JOB_ID"; cat $N/HEADS
apptainer exec --bind /cluster/medbow/gscratch $SIF bash $N/build_if_missing.sh $VER
apptainer exec --bind /cluster/medbow/gscratch $SIF bash -c "VER=$VER; source $N/env.sh; echo WM_PROJECT_VERSION=\$WM_PROJECT_VERSION; \$PY $N/extra.py $VER $N/scenx-$VER; echo extra exit \$?"
echo "exit $?"
