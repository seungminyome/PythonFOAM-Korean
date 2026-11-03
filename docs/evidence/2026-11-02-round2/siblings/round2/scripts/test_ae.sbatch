#!/bin/bash
#SBATCH --job-name=sib2-aekeras
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/siblings/round2
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/siblings/round2/logs/%x-%j.out
S=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/siblings
export PYTHONPATH=$S/pydeps/of8:$S/pydeps/tf PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OMP_NUM_THREADS=4 MPLBACKEND=Agg MPLCONFIGDIR=$S/round2/logs/mpl TF_CPP_MIN_LOG_LEVEL=1
mkdir -p $S/round2/logs/mpl $S/round2/runs/aekeras-$SLURM_JOB_ID; cd $S/round2/runs/aekeras-$SLURM_JOB_ID
/gscratch/syome/conda/s4f/bin/python3 $S/round2/scripts/test_ae_keras.py $S/upstream/Solver_Examples/AEFoam/Run_Case
echo "exit $?"
