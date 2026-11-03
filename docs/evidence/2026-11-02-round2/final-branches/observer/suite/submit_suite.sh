#!/bin/bash
# The 12B GPU suite, 1000 steps on v2212, with the tree's hpc/async_v2.slurm as the batch script, submitted from the
# detached worktree r4/observer/wt-obs (24e9df6). Its own --output lands in wt-obs/Solver_Examples/PODFoam/llm_demo/
# (llm_demo/.gitignore covers it); POD_ASYNC_OUT default = r4/observer/pod-async-v2/run-<job>.
# Pattern: r3/assemble/suite/submit_suite.sh. Usage: submit_suite.sh [--dependency=afterok:JOBID]
set -euo pipefail
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030; R=$W/r4/observer
export SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc POD_OPENFOAM_VERSION=v2212
export POD_LLM_RUNTIME=$G/PythonFOAM/llm-runtime-12b PYTHON=/gscratch/syome/conda/s4f/bin/python3
export POD_HOST_MODULES="arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0"
export POD_REFERENCE_RUN=$R/suite/ref-v2212                  # symlink written by suite/ref.sbatch to its PASSed run
export LLM_LONG_START=$W/r2/gpu-suites/start/v2212/0.1
export LLM_LONG_STEPS=1000 LLM_LONG_WRITE=250 LLM_LONG_STEP=250 LLM_LONG_SEQUENCE_STEPS=250,500,750
cd $R/wt-obs
sbatch --parsable "$@" --account=me5475 --partition=non-investor-gpu --gres=gpu:1 --constraint='l40s|a6000|a30' --cpus-per-task=8 --mem=48G \
    --time=01:30:00 --job-name=r4o-suite-v2212 --chdir=$R/wt-obs Solver_Examples/PODFoam/llm_demo/hpc/async_v2.slurm
