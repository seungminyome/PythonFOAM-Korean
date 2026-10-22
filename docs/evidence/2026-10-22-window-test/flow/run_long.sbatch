#!/bin/bash
#SBATCH --job-name=flow-long-100ms
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=04:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261022/run-long-%j.out
set -euo pipefail
module load apptainer/1.4.1
C=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261022/long-100ms
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
export FOAM_SIGFPE=true OMP_NUM_THREADS=1
cd $C && pimpleFoam > log.pimpleFoam 2>&1; echo exit \$?
grep -c '^Time = ' log.pimpleFoam; tail -3 log.pimpleFoam"
ls $C | grep -c '^0\.' || true
