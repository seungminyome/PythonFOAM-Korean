#!/bin/bash
# Quick start of llm_demo/README.md, in order, inside of-v2106-dev.sif on a compute node (pattern: pr/quick-1910/typed/steps_v2106.sh).
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; R=$W/r4/observer; D=$R/quick
export LOGS=$D/logs; mkdir -p $LOGS; source $R/tools/lib.sh
echo "node $(hostname) job $SLURM_JOB_ID cpus $(nproc) image $(grep PRETTY /etc/os-release) HEAD $(cat $D/PythonFOAM/HEAD)"
source /usr/lib/openfoam/openfoam2106/etc/bashrc
export PYTHON=/gscratch/syome/conda/s4f/bin/python3
export PATH=$(dirname "$PYTHON"):$PATH
export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
export POD_LLM_RUNTIME=$D/llm-runtime      # hard links of the E2B files fetched 2026-10-30 (pr/quick-1910/llm-runtime); no new download
export POD_LLM_PORT=$((20000 + SLURM_JOB_ID % 10000))     # not the README's 8088: the node is shared
env | grep -E '^(PYTHON|POD_|WM_PROJECT_VERSION)='
python3 --version; command -v python3
cd $D/PythonFOAM/Solver_Examples/PODFoam
cd llm_demo
python3 -m pip install --dry-run -r requirements.txt 2>&1 | tee $LOGS/pip-dry-run.log | tail -2 | cut -c1-200
if grep -q 'Would install' $LOGS/pip-dry-run.log; then echo "pip would change the env: skipped the real install"; else
  step 01-pip python3 -m pip install -r requirements.txt; fi
step 02-unittest python3 -m unittest test_llm_client test_callback test_async
cd ..
step 03-validation ./validation/run.sh
run=$(sed -n 's/^PASS: //p' $LOGS/03-validation.log | tail -1)
echo "run=$run"
observer() {
  set -x
  case=$run/observer; mkdir $case
  cp -r $run/fixed-pod/{0,constant,system} $case/
  cp llm_demo/{python_module,bounded_ipc,llm_client,pod_image,readable_image,readable_request}.py $case/
  cp validation/python_module.py $case/pod_svd.py
  LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 $run/bin/PODFoam -case $case > $case/log.PODFoam
  local st=$?
  set +x
  echo "PODFoam exit $st"; tail -3 $case/log.PODFoam
  grep -c "POD analysis callback returned" $case/log.PODFoam | sed 's/^/callback returned lines: /'
  ls $case/llm_observation/step-000005
  return $st
}
if [[ -n "$run" ]]; then step 04-observer observer; fi
step 05-setup ./llm_demo/setup_runtime.sh
step 06-start python3 llm_demo/runtime.py start
step 06b-health python3 llm_demo/runtime.py health
step 07-standalone python3 llm_demo/runtime.py standalone
step 08-demo ./llm_demo/run_demo.sh
step 09-async env POD_SUITE=async ./llm_demo/run_demo.sh
step 10-stop python3 llm_demo/runtime.py stop
cat $LOGS/steps.tsv
echo "demo dirs:"; ls -d $D/pod-llm-* 2>/dev/null
for f in $D/pod-llm-demo.*/demo-verification.json $D/pod-llm-async.*/async-verification.json; do echo "$f: $(grep -o '"status": "[A-Z]*"' $f | head -1)"; done
