#!/bin/bash
#SBATCH --job-name=flow-central-long
#SBATCH --account=me5475
#SBATCH --partition=mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261028/run-central-long-%j.out
# central-dt2e-5 of 2026-10-28 (Gauss linear for div(phi,U), deltaT 2e-5, 150 steps from the
# developed state at t = 0.1 s, finished) run again from t = 0.1 s and further:
#   central-dt2e-5-long   to t = 0.13 s (1,500 steps), every step written
#   central-dt2e-5-5000   to t = 0.2 s (5,000 steps), every 10th step written
# Both cases are copies of the original (0, 0.1, constant, system) with only endTime and
# writeInterval changed; does the run diverge, and when?
set -uo pipefail
module load apptainer
D=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261028
for c in $D/central-dt2e-5-long $D/central-dt2e-5-5000; do
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
export OMP_NUM_THREADS=1
cd $c && timeout 6000 pimpleFoam > log.pimpleFoam 2>&1; echo \"$(basename $c) exit \$?\"
grep -c '^Time = ' log.pimpleFoam; grep -E '^Courant Number' log.pimpleFoam | tail -1; tail -2 log.pimpleFoam" &
done
wait
O=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261027/unstable/central-dt2e-5
for t in 0.10002 0.1015 0.103; do
  for f in U p phi; do
    cmp -s $O/$t/$f $D/central-dt2e-5-long/$t/$f && echo "$t/$f identical to the 150-step run" || echo "$t/$f DIFFERS from the 150-step run"
  done
done
[[ -f $D/central-dt2e-5-long/0.13/U && -f $D/central-dt2e-5-5000/0.13/U ]] && cmp -s $D/central-dt2e-5-long/0.13/U $D/central-dt2e-5-5000/0.13/U && echo "0.13/U identical in both cases" || echo "0.13/U differs between the cases"
