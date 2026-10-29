#!/bin/bash
#SBATCH --job-name=flow-central-5e-6
#SBATCH --account=me5475
#SBATCH --partition=mb
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261028/run-central-dt5e-6-long-%j.out
# central-dt5e-6 of 2026-10-28 (Gauss linear for div(phi,U), deltaT 5e-6, 400 steps from the
# developed state at t = 0.1 s, finished) run again from t = 0.1 s to t = 0.12 s (4,000 steps),
# every 50th step written as before: does the same scheme stay stable at a Courant number
# below 0.5 for ten times as long? Only endTime differs from the original case.
set -uo pipefail
module load apptainer
D=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261028
c=$D/central-dt5e-6-long
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
export OMP_NUM_THREADS=1
cd $c && timeout 6000 pimpleFoam > log.pimpleFoam 2>&1; echo \"$(basename $c) exit \$?\"
grep -c '^Time = ' log.pimpleFoam; grep -E '^Courant Number' log.pimpleFoam | tail -1; tail -2 log.pimpleFoam"
O=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261027/unstable/central-dt5e-6
for t in 0.10025 0.102; do
  for f in U p phi; do
    cmp -s $O/$t/$f $c/$t/$f && echo "$t/$f identical to the 400-step run" || echo "$t/$f DIFFERS from the 400-step run"
  done
done
