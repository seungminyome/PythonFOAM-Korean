#!/bin/bash
# Inside the image. Arguments: RUN REPO VER BASHRC. Staging follows the 3D branch of version_check_inner.sh (2026-10-30).
RUN=$1 REPO=$2 VER=$3 RC=$4
set --
source "$RC" >/dev/null 2>&1 || true
set -o pipefail
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH PYTHON=$PY POD_OPENFOAM_VERSION=$VER POD_WORKSPACE=$RUN OPENFOAM_BASHRC=$RC
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
CASE3D=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/case3d
START=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/serial3d/0.10075
DEMO=$REPO/Solver_Examples/PODFoam/llm_demo
(cd "$REPO/Solver_Examples/PODFoam" && ./validation/run_v2106.sh > "$RUN/validation.log" 2>&1) && echo 'build + validation ran' || echo 'build + validation FAILED'
grep -E '^PASS|FAIL' "$RUN/validation.log" | tail -1
exe=$(ls -d "$RUN"/pod-$VER.*/bin/PODFoam | head -1); echo "exe=$exe"
[[ -x $exe ]] || exit 1
sha256sum "$exe" > "$RUN/binary-sha256.txt"
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=50 LLM_ANALYSIS_EVERY=50 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
stage() { # stage NAME Z
    local c=$RUN/$1
    mkdir -p "$c/0.10075"
    cp -r "$CASE3D/constant" "$CASE3D/system" "$c/"
    for f in U p phi; do cp "$START/$f" "$c/0.10075/"; done     # no uniform/time: the step count starts at 0
    sed 's/object      turbulenceProperties;/object      momentumTransport;/' "$c/constant/turbulenceProperties" > "$c/constant/momentumTransport"
    cp "$SRC/pod_svd.py" "$c/"
    for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do cp "$DEMO/$f" "$c/"; done
    sed -i 's/^startTime .*/startTime 0.10075;/; s/^endTime .*/endTime 0.10225;/; s/^writeInterval .*/writeInterval 50;/' "$c/system/controlDict"
    printf '%s\n' "$2" > "$c/slice-z.txt"
}
serial() { # serial NAME Z (background)
    local c=$RUN/$1 status=0
    (cd "$c" && env MPLCONFIGDIR=$c/mpl LLM_RUN_ID=r2-slice-3d/$1 POD_SLICE_Z=$2 "$exe" -case "$c" > log.PODFoam 2>&1) || status=$?
    printf '%s\n' "$status" > "$c/exit-status"; echo "$1 exit $status $(date -u +%T)"
    grep -E 'POD (observer )?plane slice|No plane slice|POD mesh geometry|Python finalized|^End|FOAM FATAL' "$c/log.PODFoam" | head -6 | cut -c1-220
}
for pair in z1:0.00079375 z3:0.00396875 z5:0.00714375 z7:0.01031250; do stage "${pair%%:*}" "${pair##*:}"; done
echo "runs start $(date -u +%T)"
for pair in z1:0.00079375 z3:0.00396875 z5:0.00714375 z7:0.01031250; do serial "${pair%%:*}" "${pair##*:}" & done
wait
for n in z1 z3 z5 z7; do echo "$n frames: $(ls -d "$RUN/$n"/llm_observation/step-* 2>/dev/null | wc -l)"; rm -f "$RUN/$n/python_svd_audit.npz"; done
echo 'runs done'
