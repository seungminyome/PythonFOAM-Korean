#!/bin/bash
# Wrapper: run setup_12b.sh from the r2/setup12b worktree for real into $L/runtime, no token.
L=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/setup12b
export POD_LLM_RUNTIME=$L/runtime PYTHON=/gscratch/syome/conda/s4f/bin/python3
unset HF_TOKEN
echo "host: $(hostname)"; echo "start: $(date -u +%FT%TZ)"; echo "HF_TOKEN set: ${HF_TOKEN:+yes}${HF_TOKEN:-no}"
echo "script sha256: $(sha256sum $L/wt/Solver_Examples/PODFoam/llm_demo/hpc/setup_12b.sh)"
echo "commit: $(git -C $L/wt rev-parse HEAD)"
/usr/bin/time -v bash -x $L/wt/Solver_Examples/PODFoam/llm_demo/hpc/setup_12b.sh
echo "exit: $?"; echo "end: $(date -u +%FT%TZ)"
