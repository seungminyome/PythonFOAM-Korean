#!/bin/bash
P=/gscratch/syome/conda/s4f; W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
O=$(ls -d $W/pr/refix/func/image-* | head -1)
source /usr/lib/openfoam/openfoam2106/etc/bashrc > /dev/null 2>&1
export PATH=$P/bin:$PATH LD_LIBRARY_PATH=$P/lib:$LD_LIBRARY_PATH POD_WORKSPACE=$O/ws
unset POD_LLM_RUNTIME
export PYTHON=$P/bin/python3
rt=$O/llm-runtime; mkdir -p $rt
port=$((20000 + ${SLURM_JOB_ID:-0} % 10000)); export POD_LLM_PORT=$port LLM_MODEL=gemma-4-E2B-it-Q4_0-vision
$W/pr/stub/llama-server --model stub --mmproj stub --alias "$LLM_MODEL" --port $port --delay 2 > $O/stub.log 2>&1 &
pid=$!; echo $pid > $rt/server.pid; sleep 3
cd $O/PythonFOAM/Solver_Examples/PODFoam
env POD_SUITE=async LLM_LONG_CASES=async-no-llm LLM_LONG_STEPS=30 LLM_LONG_STEP=5 LLM_LONG_WRITE=10 LLM_LONG_SEQUENCE_STEPS=5,10,15 ./llm_demo/run_demo.sh > $O/subset.log 2>&1; echo "exit $?"; tail -1 $O/subset.log | cut -c1-200; echo "PASS lines: $(grep -c '^PASS' $O/subset.log)"
d=$(sed -n 's/^Cases finished, not checked (LLM_LONG_CASES): //p' $O/subset.log); ls $d | head -12 | tr '\n' ' '; echo
kill $pid 2>/dev/null
