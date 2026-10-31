#!/bin/bash
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
# Environment: BRANCH_SHA
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030; R=$W/pr/refix
OUT=$R/func/image-$SLURM_JOB_ID; mkdir -p $OUT; export OUT
git clone -q --branch pr/podfoam-observer --single-branch $G/PythonFOAM $OUT/PythonFOAM; git -C $OUT/PythonFOAM rev-parse HEAD
module load apptainer
apptainer exec --bind /cluster/medbow/gscratch $W/images/of-v2106-dev.sif bash $R/jobs/func_v2106.sh
echo "v2106 exit $?"
apptainer exec --bind /cluster/medbow/gscratch $W/images/of-8.sif bash $R/jobs/func_of8.sh
echo "of8 exit $?"
