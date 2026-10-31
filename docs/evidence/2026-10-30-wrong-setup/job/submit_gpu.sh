#!/bin/bash
# The GPU job of the wrong-setup test: window_test.slurm with PICTURE_TEST_SCRIPT=wrong_setup_test.py and the
# four models of the instability test in one job on one GPU. Same server settings as that test (context 4096,
# batch and ubatch 512, 256 image tokens, one slot); seed 20261021, max_tokens 320, temperature 0 and no prompt
# cache are in the request bodies. L40S or A6000 only (48 GB; Qwen3.5-35B-A3B Q8_0 is 35 GB): non-investor-gpu
# reaches the same L40S nodes as mb-l40s and the feature keeps out its T4 and A30 nodes.
set -euo pipefail
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup
cd "$HERE"
export POD_SOURCE=$REPO/Solver_Examples/PODFoam
export POD_LLM_RUNTIME=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM/llm-runtime-12b
export PICTURE_TEST_SET=$HERE/wrong-setup-test-20261030 PICTURE_TEST_SCRIPT=wrong_setup_test.py
export POD_HOST_MODULES="arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0"
export PATH=/gscratch/syome/conda/s4f/bin:$PATH
export MODELS="12b 26b 31b qwen35-35b"
sbatch --parsable --account=me5475 --partition=non-investor-gpu,mb-a6000 --constraint='l40s|a6000' --gres=gpu:1 --time=03:00:00 \
    --chdir="$HERE" --output="$HERE/pod-window-test-%j.out" "$POD_SOURCE/llm_demo/hpc/window_test.slurm"
