#!/bin/bash
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
N=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/refix/cpp
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
module load apptainer
export WM_NCOMPPROCS=4
case $VER in v2106) SIF=$W/images/of-v2106-dev.sif;; 8) SIF=$W/images/of-8.sif;; esac
apptainer exec --bind /cluster/medbow/gscratch $SIF bash $N/build_inner.sh $VER
apptainer exec --bind /cluster/medbow/gscratch $SIF bash -c "VER=$VER; source $N/env.sh; \$PY $N/scenarios.py $VER $N/scen-$VER; echo scenarios exit \$?; \$PY $N/schedule.py $VER $N/sched-$VER; echo schedule exit \$?"
echo "exit $?"
