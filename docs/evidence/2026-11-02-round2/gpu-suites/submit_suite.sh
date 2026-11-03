#!/bin/bash
# docs/evidence/2026-10-30-versions/scripts/gpu/submit_suite.sh (job 24950817) with the image, bashrc, version and
# reference run as arguments. Usage: submit_suite.sh VER short|default
#   short   : LLM_LONG_STEPS=1000, write/request 250, sequence 250,500,750 (the settings of 24950817), worktree r2/gpu-suites (c82c835)
#   default : no LLM_LONG_* override, the unedited bf7a06e worktree
# Beyond hpc/README.md: --constraint, --time, --chdir, --output.
set -euo pipefail
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030; R=$W/r2/gpu-suites
VER=$1 MODE=$2
case $VER in
  v2012) export SIF=$W/images/of-v2012-dev.sif OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2212) export SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     export SIF=$W/images/of-8.sif OPENFOAM_BASHRC=/opt/openfoam8/etc/bashrc;;
esac
export POD_OPENFOAM_VERSION=$VER
export POD_LLM_RUNTIME=$G/PythonFOAM/llm-runtime-12b PYTHON=/gscratch/syome/conda/s4f/bin/python3
export POD_HOST_MODULES="arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0"
export POD_REFERENCE_RUN=$(ls -dt $R/ref/pod-$VER.* | head -1)
grep -q '"status": "PASS"' $POD_REFERENCE_RUN/verification.json
if [[ $MODE == short ]]; then
  root=$R/wt
  export LLM_LONG_START=$R/start/$VER/0.1
  export LLM_LONG_STEPS=1000 LLM_LONG_WRITE=250 LLM_LONG_STEP=250 LLM_LONG_SEQUENCE_STEPS=250,500,750
  time=01:30:00
else
  root=$R/wt-bf7a06e
  export LLM_LONG_START=$G/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm/0.1
  time=03:00:00
fi
cd $root
sbatch --parsable --account=me5475 --partition=non-investor-gpu --gres=gpu:1 --constraint='l40s|a6000|a30' --cpus-per-task=8 --mem=48G \
    --time=$time --job-name=pod-async-$VER-$MODE --chdir=$root --output=$R/slurm/pod-async-v2-$VER-$MODE-%j.out \
    Solver_Examples/PODFoam/llm_demo/hpc/async_v2.slurm
