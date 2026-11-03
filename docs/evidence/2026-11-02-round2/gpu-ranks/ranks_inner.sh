#!/bin/bash
# Runs inside the image. Arguments: OUT REPO VER BASHRC PORT. Staging as pr/refix/gpu-a/part_a_inner.sh; the 2-rank
# case as matrix/version_check_inner.sh (rank check taken out of the case's pod_svd.py, scotch on 2 subdomains).
OUT=$1 REPO=$2 VER=$3 RC=$4 PORT=$5
set --    # the openfoam.com bashrc reads the positional parameters
source "$RC" >/dev/null 2>&1 || true
set -o pipefail
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH PYTHON=$PY POD_OPENFOAM_VERSION=$VER POD_WORKSPACE=$OUT OPENFOAM_BASHRC=$RC
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
DEMO=$REPO/Solver_Examples/PODFoam/llm_demo
A=$(dirname "$(readlink -f "$0")")
(cd "$REPO/Solver_Examples/PODFoam" && ./validation/run_v2106.sh > "$OUT/validation.log" 2>&1) && echo 'build + validation ran' || echo 'build + validation FAILED'
tail -1 "$OUT/validation.log" | cut -c1-200
exe=$(ls -d "$OUT"/pod-$VER.*/bin/PODFoam | head -1); echo "exe=$exe"
[[ -x $exe ]] || exit 1
sha256sum "$exe" > "$OUT/binary-sha256.txt"
command -v mpirun > "$OUT/mpirun-path.txt"; mpirun --version > "$OUT/mpirun-version.txt" 2>&1
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export LLM_ENABLED=1 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=100 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
export LLM_ENDPOINT=http://127.0.0.1:$PORT/v1/chat/completions LLM_MODEL=gemma-4-12b-it-qat-q4_0-vision LLM_TIMEOUT_S=120 LLM_MAX_TOKENS=320 LLM_KILL_JOIN_S=0.2
metrics() { "$PY" -c "import urllib.request,sys; sys.stdout.write(urllib.request.urlopen('http://127.0.0.1:$PORT/metrics', timeout=10).read().decode())" > "$1" 2>&1; }
stage() { # stage NAME
    local c=$OUT/$1; mkdir -p "$c"
    for d in 0 constant system 0.1; do cp -r "$SRC/$d" "$c/"; done
    sed 's/object      turbulenceProperties;/object      momentumTransport;/' "$c/constant/turbulenceProperties" > "$c/constant/momentumTransport"
    if [[ $VER != v* ]]; then sed -i '/libincompressibleTurbulenceModels/d' "$c/system/controlDict"; fi
    cp "$SRC/pod_svd.py" "$c/"
    for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do cp "$DEMO/$f" "$c/"; done
    sed -i 's/^endTime .*/endTime 0.10055;/; s/^writeInterval .*/writeInterval 250;/' "$c/system/controlDict"
}
report() { # report CASE STATUS
    echo "$1 exit $2"; printf '%s\n' "$2" > "$OUT/$1/exit-status"
    grep -E 'POD mesh geometry|Python finalized|^End|FOAM FATAL' "$OUT/$1/log.PODFoam" | head -6 | cut -c1-200
}
# serial, as job 24950818
stage serial; c=$OUT/serial; status=0
metrics "$c/metrics-before.txt"; 
date -u +%FT%T.%NZ > "$c/started-at.txt"
(cd "$c" && env MPLCONFIGDIR=$c/mpl LLM_RUN_ID=gpu-ranks/$VER/serial "$exe" -case "$c" > log.PODFoam 2>&1) || status=$?
date -u +%FT%T.%NZ > "$c/ended-at.txt"
metrics "$c/metrics-after.txt"
report serial $status
# 2 MPI ranks
stage par2; c=$OUT/par2; status=0
sed -i 's/if rank != 0:/if False:/; s/if rank != 0 or not _snapshots:/if not _snapshots:/' "$c/pod_svd.py"
sed -i 's/^numberOfSubdomains .*/numberOfSubdomains 2;/; s/^method .*/method scotch;/' "$c/system/decomposeParDict"
metrics "$c/metrics-before.txt"
date -u +%FT%T.%NZ > "$c/started-at.txt"
(cd "$c" && decomposePar -case "$c" > log.decomposePar 2>&1 \
  && env MPLCONFIGDIR=$c/mpl LLM_RUN_ID=gpu-ranks/$VER/par2 CASE=$c mpirun --oversubscribe -np 2 bash "$A/rank_wrap.sh" "$exe" -parallel -case "$c" > log.mpirun 2>&1) || status=$?
date -u +%FT%T.%NZ > "$c/ended-at.txt"
metrics "$c/metrics-after.txt"
report par2 $status
tail -3 "$c/log.decomposePar" | cut -c1-160; cat "$c"/rank-*.txt; ls "$c" | tr '\n' ' '; echo
