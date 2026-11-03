#!/bin/bash
#SBATCH --job-name=r4f-scen
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --exclude=t527
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/scenarios
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/scenarios/slurm/scen-%x-%j.out
# scenarios.py + schedule.py + extra.py at the r4/pr-observer tip (src/fork) against the base 6fde869 (src/upstream); VER in env.
N=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/scenarios
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
module load apptainer
export WM_NCOMPPROCS=4
case $VER in v2012) SIF=$W/images/of-v2012-dev.sif;; v2106) SIF=$W/images/of-v2106-dev.sif;; v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif;; 8) SIF=$W/images/of-8.sif;; esac
echo "VER $VER SIF $SIF node $(hostname) job $SLURM_JOB_ID"; cat $N/HEADS
apptainer exec --bind /cluster/medbow/gscratch $SIF bash $N/build_inner.sh $VER
apptainer exec --bind /cluster/medbow/gscratch $SIF bash -c "VER=$VER; source $N/env.sh; echo WM_PROJECT_VERSION=\$WM_PROJECT_VERSION; \$PY $N/scenarios.py $VER $N/scen-$VER; echo scenarios exit \$?; \$PY $N/schedule.py $VER $N/sched-$VER; echo schedule exit \$?; \$PY $N/extra.py $VER $N/scenx-$VER; echo extra exit \$?"
echo "exit $?"
