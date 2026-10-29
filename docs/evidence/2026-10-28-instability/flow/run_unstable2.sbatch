#!/bin/bash
#SBATCH --job-name=flow-unstable2
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261027/run-unstable2-%j.out
# Central differencing between the Courant numbers that finished (1.54) and crashed at step 1 (4.5):
# does a run go wrong over several steps?
set -uo pipefail
module load apptainer
U=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261027/unstable
for c in $U/central-dt3e-5 $U/central-dt4e-5 $U/central-dt5e-5 $U/central-dt6e-5; do
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
export OMP_NUM_THREADS=1
cd $c && timeout 1500 pimpleFoam > log.pimpleFoam 2>&1; echo \"$(basename $c) exit \$?\"
grep -c '^Time = ' log.pimpleFoam; grep -E '^Courant Number' log.pimpleFoam | tail -1; tail -2 log.pimpleFoam" &
done
wait
