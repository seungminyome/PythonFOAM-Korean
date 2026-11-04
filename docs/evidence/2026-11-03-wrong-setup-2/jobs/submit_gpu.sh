#!/bin/bash
# The GPU job of wrong-setup test 2: window_test.slurm with PICTURE_TEST_SCRIPT=wrong_setup_test2.py,
# Gemma 4 31B only, on one L40S or A6000 (48 GB). The six request sets (stated/blind x t0/t07a/t07b)
# are answered in one job. Usage: bash submit_gpu.sh <test set dir> [models]
set -euo pipefail
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-2-20261103
REPO=$HERE/repo
SET=${1:?test set}
cd "$HERE"
export POD_SOURCE=$REPO/Solver_Examples/PODFoam
export POD_LLM_RUNTIME=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM/llm-runtime-12b
export PICTURE_TEST_SET=$SET PICTURE_TEST_SCRIPT=wrong_setup_test2.py
export POD_HOST_MODULES="arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0"
export PATH=/gscratch/syome/conda/s4f/bin:$PATH
export MODELS="${2:-31b}"
mkdir -p "$HERE/results"
sbatch --parsable --account=me5475 --partition=non-investor-gpu,mb-a6000 --constraint='l40s|a6000' --gres=gpu:1 --time=06:00:00 \
    --chdir="$HERE" --output="$HERE/results/pod-window-test-%j.out" "$POD_SOURCE/llm_demo/hpc/window_test.slurm"
