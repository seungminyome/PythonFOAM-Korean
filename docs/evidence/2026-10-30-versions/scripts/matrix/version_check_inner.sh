#!/bin/bash
# Runs inside the image. Arguments: OUT REPO VER BASHRC
OUT=$1 REPO=$2 VER=$3 RC=$4
set --    # the openfoam.com bashrc reads the positional parameters and would source the file named in them
source "$RC" >/dev/null 2>&1 || true
set -o pipefail
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH PYTHON=$PY POD_OPENFOAM_VERSION=$VER POD_WORKSPACE=$OUT OPENFOAM_BASHRC=$RC
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
CASE3D=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/case3d
DEMO=$REPO/Solver_Examples/PODFoam/llm_demo
(cd "$REPO/Solver_Examples/PODFoam" && ./validation/run_v2106.sh > "$OUT/validation.log" 2>&1) && echo 'validation ran' || echo 'validation FAILED'
grep -E '^PASS|FAIL' "$OUT/validation.log" | tail -1
exe=$(ls -d "$OUT"/pod-$VER.*/bin/PODFoam | head -1); echo "exe=$exe"
[[ -x $exe ]] || exit 1
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=100 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
stage() { # stage NAME 2d|3d
    local c=$OUT/$1 kind=$2
    mkdir -p "$c"
    if [[ $kind == 2d ]]; then for d in 0 constant system 0.1; do cp -r "$SRC/$d" "$c/"; done
    else cp -r "$CASE3D/constant" "$CASE3D/system" "$CASE3D/0.1" "$c/"; fi
    # openfoam.org reads momentumTransport: the same settings as turbulenceProperties
    sed 's/object      turbulenceProperties;/object      momentumTransport;/' "$c/constant/turbulenceProperties" > "$c/constant/momentumTransport"
    if [[ $VER != v* ]]; then sed -i '/libincompressibleTurbulenceModels/d' "$c/system/controlDict"; fi
    cp "$SRC/pod_svd.py" "$c/"
    for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do cp "$DEMO/$f" "$c/"; done
    sed -i 's/^endTime .*/endTime 0.10055;/; s/^writeInterval .*/writeInterval 250;/' "$c/system/controlDict"
}
serial() { # serial NAME
    local c=$OUT/$1 status=0
    (cd "$c" && env MPLCONFIGDIR=$c/mpl LLM_RUN_ID=version-check/$VER/$1 "$exe" -case "$c" > log.PODFoam 2>&1) || status=$?
    echo "$1 exit $status"; printf '%s\n' "$status" > "$c/exit-status"
    grep -E 'POD (observer )?plane slice|No plane slice|POD mesh geometry|Python finalized|^End|FOAM FATAL' "$c/log.PODFoam" | head -6 | cut -c1-200
}
parallel() { # parallel NAME
    local c=$OUT/$1 status=0
    # the case's POD module refuses ranks other than 0; this copy keeps per-rank snapshots
    sed -i 's/if rank != 0:/if False:/; s/if rank != 0 or not _snapshots:/if not _snapshots:/' "$c/pod_svd.py"
    sed -i 's/^numberOfSubdomains .*/numberOfSubdomains 2;/; s/^method .*/method scotch;/' "$c/system/decomposeParDict"
    (cd "$c" && decomposePar -case "$c" > log.decomposePar 2>&1 && env MPLCONFIGDIR=$c/mpl LLM_RUN_ID=version-check/$VER/$1 mpirun --oversubscribe -np 2 "$exe" -parallel -case "$c" > log.PODFoam 2>&1) || status=$?
    echo "$1 exit $status"; printf '%s\n' "$status" > "$c/exit-status"
    grep -E 'POD (observer )?plane slice|No plane slice|POD mesh geometry|Python finalized|^End|FOAM FATAL' "$c/log.PODFoam" | head -6 | cut -c1-200
    tail -3 "$c/log.decomposePar" | cut -c1-160
}
stage serial2d 2d; serial serial2d
stage serial3d 3d; serial serial3d
stage par2d 2d; parallel par2d
stage par3d 3d; parallel par3d
echo 'runs done'
