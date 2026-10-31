#!/bin/bash
# Runs inside the image. Arguments: OUT REPO VER BASHRC PORT. The staging is the 2D branch of matrix/version_check_inner.sh.
OUT=$1 REPO=$2 VER=$3 RC=$4 PORT=$5
set --    # the openfoam.com bashrc reads the positional parameters
source "$RC" >/dev/null 2>&1 || true
set -o pipefail
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH PYTHON=$PY POD_OPENFOAM_VERSION=$VER POD_WORKSPACE=$OUT OPENFOAM_BASHRC=$RC
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
DEMO=$REPO/Solver_Examples/PODFoam/llm_demo
(cd "$REPO/Solver_Examples/PODFoam" && ./validation/run_v2106.sh > "$OUT/validation.log" 2>&1) && echo 'build + validation ran' || echo 'build + validation FAILED'
tail -1 "$OUT/validation.log" | cut -c1-200
exe=$(ls -d "$OUT"/pod-$VER.*/bin/PODFoam | head -1); echo "exe=$exe"
[[ -x $exe ]] || exit 1
sha256sum "$exe" > "$OUT/binary-sha256.txt"
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export LLM_ENABLED=1 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=100 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
export LLM_ENDPOINT=http://127.0.0.1:$PORT/v1/chat/completions LLM_MODEL=gemma-4-12b-it-qat-q4_0-vision LLM_TIMEOUT_S=120 LLM_MAX_TOKENS=320 LLM_KILL_JOIN_S=0.2
c=$OUT/case2d; mkdir -p "$c"
for d in 0 constant system 0.1; do cp -r "$SRC/$d" "$c/"; done
sed 's/object      turbulenceProperties;/object      momentumTransport;/' "$c/constant/turbulenceProperties" > "$c/constant/momentumTransport"
if [[ $VER != v* ]]; then sed -i '/libincompressibleTurbulenceModels/d' "$c/system/controlDict"; fi
cp "$SRC/pod_svd.py" "$c/"
for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do cp "$DEMO/$f" "$c/"; done
sed -i 's/^endTime .*/endTime 0.10055;/; s/^writeInterval .*/writeInterval 250;/' "$c/system/controlDict"
status=0
(cd "$c" && env MPLCONFIGDIR=$c/mpl LLM_RUN_ID=gpu-versions/$VER/case2d "$exe" -case "$c" > log.PODFoam 2>&1) || status=$?
echo "case2d exit $status"; printf '%s\n' "$status" > "$c/exit-status"
grep -E 'POD mesh geometry|Python finalized|^End|FOAM FATAL' "$c/log.PODFoam" | head -6 | cut -c1-200
