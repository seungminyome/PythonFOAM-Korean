#!/bin/bash
#SBATCH --job-name=flow-upwind-long
#SBATCH --account=me5475
#SBATCH --partition=mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261028/run-upwind-long-%j.out
# The two upwind runs of 2026-10-28 (Gauss upwind for div(phi,U); deltaT 2e-5 and 4e-5; 400 steps
# from the developed state at t = 0.1 s, finished) run again from t = 0.1 s for 2,000 steps
# (to t = 0.14 s and 0.18 s), every 10th step written as before. central-dt2e-5 finished its
# first 150 steps and crashed in step 467, so 400 steps without a crash do not show that a run
# stays stable; only endTime differs from the original cases.
set -uo pipefail
module load apptainer
D=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261028
for c in $D/upwind-dt2e-5-long $D/upwind-dt4e-5-long; do
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
export OMP_NUM_THREADS=1
cd $c && timeout 6000 pimpleFoam > log.pimpleFoam 2>&1; echo \"$(basename $c) exit \$?\"
grep -c '^Time = ' log.pimpleFoam; grep -E '^Courant Number' log.pimpleFoam | tail -1; tail -2 log.pimpleFoam" &
done
wait
O=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261027/unstable
for pair in dt2e-5:upwind-dt2e-5-long:0.108 dt4e-5:upwind-dt4e-5-long:0.116; do
  IFS=: read src dst t <<< "$pair"
  for f in U p phi; do
    cmp -s $O/$src/$t/$f $D/$dst/$t/$f && echo "$dst $t/$f identical to the 400-step run" || echo "$dst $t/$f DIFFERS from the 400-step run"
  done
done
