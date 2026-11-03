#!/bin/bash
#SBATCH --job-name=r4o-quick
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer/logs/quick-%j.out
# Quick start of llm_demo/README.md (E2B, CPU) on v2106 on the r4/pr-observer export (quick/PythonFOAM).
# Pattern: r3/assemble/jobs/quick.sbatch.
module load apptainer
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
apptainer exec --bind /cluster/medbow/gscratch $W/images/of-v2106-dev.sif bash $W/r4/observer/jobs/quick_steps.sh
