#!/bin/bash
#SBATCH --job-name=refix-quick
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=02:00:00
module load apptainer
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
apptainer exec --bind /cluster/medbow/gscratch $W/images/of-v2106-dev.sif bash $W/pr/refix/jobs/quick_steps.sh
