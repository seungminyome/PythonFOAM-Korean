#!/bin/bash
# Runs inside the OpenFOAM v2212 image (slice_test.sbatch): build PODFoam and run the 2D bridge
# validation, make the 3D step case, then the solver runs of the 2026-10-28 slice test.
# Arguments: OUT REPO SRC
#   OUT  run folder; REPO the observer-3d worktree; SRC the staged 2D step case (developed flow at t = 0.1 s)
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
set -eo pipefail   # not -u: the OpenFOAM bashrc reads unset variables
OUT=$1 REPO=$2 SRC=$3
PY=/gscratch/syome/conda/s4f/bin/python3
DEMO=$REPO/Solver_Examples/PODFoam/llm_demo
EVID=$REPO/docs/evidence/2026-10-28-3d
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH PYTHON=$PY POD_OPENFOAM_VERSION=v2212

# 1. build and 2D bridge validation (serial, ten steps, no observer)
export POD_WORKSPACE=$OUT
(cd "$REPO/Solver_Examples/PODFoam" && ./validation/run_v2106.sh > "$OUT/validation.log" 2>&1) \
    && echo 'validation ran' || echo 'validation FAILED'
grep -E 'PASS|FAIL' "$OUT/validation.log" | tail -2 || true
exe=$(ls -d "$OUT"/pod-v2212.*/bin/PODFoam | head -1); echo "exe=$exe"

# 2. the 3D case: blockMesh with 8 cells in z and walls front and back, the 2D state at t = 0.1 s
#    copied into every layer, cell map checked with OpenFOAM's cell centres
base=$OUT/case3d; mkdir -p "$base/constant" "$base/system"
cp -r "$SRC/system/." "$base/system/"
for f in transportProperties turbulenceProperties momentumTransport; do cp "$SRC/constant/$f" "$base/constant/"; done
$PY "$EVID/make_case3d.py" dict "$SRC" "$base" --nz 8
blockMesh -case "$base" > "$base/log.blockMesh" 2>&1
checkMesh -case "$base" > "$base/log.checkMesh" 2>&1 || true
grep -E 'cells:|Mesh OK|Failed' "$base/log.checkMesh" | head -3 || true
$PY "$EVID/make_case3d.py" fields "$SRC" "$base" --nz 8 --time 0.1
copy2d=$OUT/centres2d; mkdir -p "$copy2d"
cp -r "$SRC/constant" "$SRC/system" "$copy2d/"; mkdir -p "$copy2d/0.1"; cp "$SRC/0.1/U" "$SRC/0.1/p" "$copy2d/0.1/"
postProcess -case "$copy2d" -func writeCellCentres -time 0.1 > "$copy2d/log.writeCellCentres" 2>&1
postProcess -case "$base" -func writeCellCentres -time 0.1 > "$base/log.writeCellCentres" 2>&1
$PY "$EVID/make_case3d.py" check "$copy2d" "$base" "$OUT/case3d-check.json" --time 0.1
rm -f "$base"/0.1/C "$base"/0.1/Cx "$base"/0.1/Cy "$base"/0.1/Cz
ls "$base/0.1"

# 3. solver runs: the observer with v2 pictures and no model, frame at step 100
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=100 \
       LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
stage() {   # stage NAME FROM STEPS WRITE OBSERVER: a case folder of NAME from FROM (3d: case3d, 2d: SRC)
    local c=$OUT/$1 from=$2 steps=$3 write=$4 observer=$5
    mkdir -p "$c"
    if [[ $from == 3d ]]; then
        cp -r "$base/constant" "$base/system" "$base/0.1" "$c/"
    else
        for d in 0 constant system 0.1; do cp -r "$SRC/$d" "$c/"; done
    fi
    cp "$SRC/pod_svd.py" "$c/"
    if [[ $observer == 1 ]]; then
        for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do
            cp "$DEMO/$f" "$c/"
        done
    else
        cp "$SRC/pod_svd.py" "$c/python_module.py"   # no analysis_func: no observer, no gathers, no slice
    fi
    sed -i "s/^endTime .*/endTime $($PY -c "print(round(0.1 + $steps * 5e-6, 10))");/; s/^writeInterval .*/writeInterval $write;/" "$c/system/controlDict"
}
serial() {   # serial NAME [env assignments]: run PODFoam serially in OUT/NAME
    local c=$OUT/$1 status=0; shift
    (cd "$c" && env MPLCONFIGDIR=$c/mpl LLM_RUN_ID=slice-test/$(basename "$c") "$@" "$exe" -case "$c" > log.PODFoam 2>&1) || status=$?
    echo "$(basename "$c") exit $status"
    grep -E 'POD observer plane slice|No plane slice|POD mesh geometry|PYTHON LLM mesh|PYTHON LLM step|callback failed|Python finalized|^End' "$c/log.PODFoam" | head -8 || true
}

stage serial3d 3d 150 50 1
serial serial3d

stage par3d 3d 150 50 1
# the case's POD module refuses ranks other than 0; this copy keeps per-rank snapshots instead
sed -i 's/if rank != 0:/if False:/; s/if rank != 0 or not _snapshots:/if not _snapshots:/' "$OUT/par3d/pod_svd.py"
sed -i 's/^numberOfSubdomains .*/numberOfSubdomains 2;/; s/^method .*/method scotch;/' "$OUT/par3d/system/decomposeParDict"
status=0
(cd "$OUT/par3d" && decomposePar -case "$OUT/par3d" > log.decomposePar 2>&1 \
    && env MPLCONFIGDIR=$OUT/par3d/mpl LLM_RUN_ID=slice-test/par3d mpirun --oversubscribe -np 2 "$exe" -parallel -case "$OUT/par3d" > log.PODFoam 2>&1) || status=$?
echo "par3d exit $status"
reconstructPar -case "$OUT/par3d" > "$OUT/par3d/log.reconstructPar" 2>&1 || echo 'reconstructPar failed'
grep -E 'POD observer plane slice|POD mesh geometry|PYTHON LLM mesh|PYTHON LLM step|Python finalized|^End' "$OUT/par3d/log.PODFoam" | head -6 || true

stage noobs3d 3d 150 50 0
serial noobs3d

stage slicez3d 3d 10 50 1
serial slicez3d LLM_SLICE_Z=0.002 LLM_ANALYSIS_STEP=5

stage badz3d 3d 4 50 1
serial badz3d LLM_SLICE_Z=abc LLM_ANALYSIS_STEP=2
stage outz3d 3d 4 50 1
serial outz3d LLM_SLICE_Z=1.0 LLM_ANALYSIS_STEP=2

stage serial2d 2d 120 250 1
serial serial2d
echo 'runs done'
