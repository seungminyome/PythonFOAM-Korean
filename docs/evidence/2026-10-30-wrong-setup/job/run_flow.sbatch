#!/bin/bash
#SBATCH --job-name=wrong-setup-flow
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
#SBATCH --array=0-9
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261030/jobs/run-flow-%A_%a.out
# One of the ten runs of the wrong-setup test: pimpleFoam (v2212 image), 8,000 steps of 5e-6 s from
# t = 0.1 s, every 500th step written; the settings of flow-states-20261022/long-100ms otherwise.
set -uo pipefail
module load apptainer
D=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261030
cases=(N1 N2 N3 N4 N5 M1-inlet-speed M2-viscosity M3-slip-walls M4-moving-wall M5-half-inlet)
c=$D/${cases[$SLURM_ARRAY_TASK_ID]}
hostname; date; echo "$c"
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
export FOAM_SIGFPE=true OMP_NUM_THREADS=1
cd $c && timeout 6600 pimpleFoam > log.pimpleFoam 2>&1; echo \"$(basename $c) exit \$?\"
grep -c '^Time = ' log.pimpleFoam; grep -E '^Courant Number' log.pimpleFoam | tail -1; tail -3 log.pimpleFoam"
date
