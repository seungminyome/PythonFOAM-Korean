#!/bin/bash
# hpc/README.md "the job" from the repository root, with a short run. Beyond the README: --constraint (this partition also holds T4 and A30 nodes), --time, --chdir, --output.
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030; B=$W/pr/refix/gpu-b
cd $B/PythonFOAM || exit 1
export POD_LLM_RUNTIME=$G/PythonFOAM/llm-runtime-12b PYTHON=/gscratch/syome/conda/s4f/bin/python3
export SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif POD_HOST_MODULES="arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0"
export POD_REFERENCE_RUN=$(ls -d $B/pod-v2212.* | tail -1)
export LLM_LONG_START=$G/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm/0.1
export LLM_LONG_STEPS=1000 LLM_LONG_WRITE=250 LLM_LONG_STEP=250 LLM_LONG_SEQUENCE_STEPS=250,500,750
sbatch --parsable --account=me5475 --partition=non-investor-gpu,mb-a6000 --constraint='l40s|a6000' --time=01:30:00 \
    --chdir=$PWD --output=$PWD/pod-async-v2-%j.out Solver_Examples/PODFoam/llm_demo/hpc/async_v2.slurm
