#!/bin/bash
# v2106 image (it has no python3).
P=/gscratch/syome/conda/s4f; W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
cd $OUT/PythonFOAM/Solver_Examples/PODFoam
echo "=== no OpenFOAM sourced, no Python anywhere"
env -u PYTHON POD_WORKSPACE=$OUT/ws0 ./validation/run_v2106.sh; echo "exit $?"; ls $OUT/ws0 2>/dev/null | wc -l
source /usr/lib/openfoam/openfoam2106/etc/bashrc > /dev/null 2>&1
export PATH=$P/bin:$PATH LD_LIBRARY_PATH=$P/lib:$LD_LIBRARY_PATH POD_WORKSPACE=$OUT/ws; mkdir -p $POD_WORKSPACE
echo "=== v2106 sourced, no variable set"
./validation/run_v2106.sh > $OUT/validation.log 2>&1; echo "exit $?"; tail -1 $OUT/validation.log | cut -c1-200
run=$(sed -n 's/^PASS: //p' $OUT/validation.log); echo "baseline: exit-status $(cat $run/baseline-pimple/exit-status)"
echo "=== POD_WORKSPACE set, POD_LLM_RUNTIME unset, runtime beside the checkout (stand-in server), LLM_LONG_CASES subset"
rt=$OUT/llm-runtime; mkdir -p $rt
port=$((20000 + ${SLURM_JOB_ID:-0} % 10000)); export POD_LLM_PORT=$port LLM_MODEL=gemma-4-E2B-it-Q4_0-vision
python3 $W/pr/stub/llama-server --model stub --mmproj stub --alias "$LLM_MODEL" --port $port --delay 2 > $OUT/stub.log 2>&1 &
pid=$!; echo $pid > $rt/server.pid; sleep 3
env POD_SUITE=async LLM_LONG_CASES=async-no-llm LLM_LONG_STEPS=30 LLM_LONG_STEP=5 LLM_LONG_WRITE=10 LLM_LONG_SEQUENCE_STEPS=5,10,15 ./llm_demo/run_demo.sh > $OUT/subset.log 2>&1; echo "exit $?"; tail -1 $OUT/subset.log | cut -c1-200; grep -c '^PASS' $OUT/subset.log
d=$(sed -n 's/^Cases finished, not checked (LLM_LONG_CASES): //p' $OUT/subset.log); ls $d | head -8 | tr '\n' ' '; echo
kill $pid 2>/dev/null
echo "=== POD_SLICE_Z on the 3D case"
CASE3D=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/case3d
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
c=$OUT/case3d; mkdir -p $c; cp -r $CASE3D/constant $CASE3D/system $CASE3D/0.1 $c/; cp $SRC/pod_svd.py $c/
for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do cp llm_demo/$f $c/; done
sed -i 's/^endTime .*/endTime 0.10002;/; s/^writeInterval .*/writeInterval 250;/' $c/system/controlDict
(cd $c && env MPLCONFIGDIR=$c/mpl LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=2 POD_SLICE_Z=0.002 $run/bin/PODFoam -case $c > log.PODFoam 2>&1; echo "exit $?")
grep -E 'POD plane slice|No plane slice|POD mesh geometry|^End' $c/log.PODFoam | cut -c1-200
python3 -c "import json,sys; print(json.load(open('$c/llm_observation/step-000002/readable-metadata.json')).get('slice'))"
c2=$OUT/case3d-bad; cp -r $c $c2; rm -rf $c2/llm_observation $c2/llm_*.json* $c2/telemetry*
(cd $c2 && env MPLCONFIGDIR=$c2/mpl LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=2 POD_SLICE_Z=abc $run/bin/PODFoam -case $c2 > log.PODFoam 2>&1; echo "exit $?")
grep -E 'POD_SLICE_Z|^End' $c2/log.PODFoam | cut -c1-200
