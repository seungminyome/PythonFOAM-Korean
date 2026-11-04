#!/bin/bash
#SBATCH --job-name=ws2-flow
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=02:00:00
# One pimpleFoam run (v2212 image) of a wrong-setup-2 case folder: 8,000 steps of 5e-6 s from
# t = 0.1 s, every 500th step written. Usage: sbatch --array=0-N --chdir=<cases> --output=... run_flow.sbatch
# The case list is design.json's run order.
set -uo pipefail
module load apptainer
D=${SLURM_SUBMIT_DIR}
mapfile -t cases < <(python3 -c "import json,sys; [print(r['case']) for r in json.load(open('$D/design.json'))['runs']]")
c=${cases[$SLURM_ARRAY_TASK_ID]}
hostname; date; echo "$c"
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
export FOAM_SIGFPE=true OMP_NUM_THREADS=1
cd $c && timeout 6600 pimpleFoam > log.pimpleFoam 2>&1; echo \"$(basename $c) exit \$?\"
grep -c '^Time = ' log.pimpleFoam; grep -E '^Courant Number' log.pimpleFoam | tail -1; tail -3 log.pimpleFoam"
date
