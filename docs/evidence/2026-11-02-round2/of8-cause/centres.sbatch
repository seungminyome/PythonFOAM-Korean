#!/bin/bash
#SBATCH --job-name=of8-cause-C
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:20:00
# Writes the cell centres (field C) at 0.1005 of the finished v2212 3D run, in the v2212 image.
set -uo pipefail
R=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/of8-cause
module load apptainer
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c '
set --; source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1
cd '"$R"'/runs/v2212-3d-25080024/A && postProcess -func writeCellCentres -time 0.1005 > log.writeCellCentres 2>&1; echo "postProcess exit $?"; ls 0.1005'
