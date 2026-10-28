#!/bin/bash
#SBATCH --job-name=pod-cylinder
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261027/run-cylinder-pod-%j.out
set -uo pipefail
module load apptainer
P=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261027/cylinder-pod
BIN=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/llm-demo-work/bin/PODFoam
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:\$LD_LIBRARY_PATH PYTHON=/gscratch/syome/conda/s4f/bin/python3
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=$P/mpl OPENBLAS_NUM_THREADS=1
export LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=1 LLM_RUN_ID=cylinder-pod
cd $P && $BIN -case $P > log.PODFoam 2>&1; echo \"exit \$?\"
grep -c '^Time = ' log.PODFoam; grep -E 'PYTHON LLM|POD mesh' log.PODFoam | head -5; tail -3 log.PODFoam"
ls $P/llm_observation 2>/dev/null; ls $P | grep -c '^1[56]'
