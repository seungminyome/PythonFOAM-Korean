#!/bin/bash
OUT=$1 VER=$2 RC=$3
set --    # the openfoam.com bashrc reads the positional parameters and would source the file named in them
source "$RC" >/dev/null 2>&1 || true
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH
export PYTHON_INCLUDE_PATH=$($PY -c 'import sysconfig; print(sysconfig.get_path("include"))')
export NUMPY_INCLUDE_PATH=$($PY -c 'import numpy; print(numpy.get_include())')
export PYTHON_LIB_PATH=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
export PYTHON_LIB_NAME=lpython$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LDVERSION"))')
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
build() { # build SOURCE
    local src=$OUT/src-$1/Solver_Examples/PODFoam
    export FOAM_USER_APPBIN=$OUT/bin-$1; mkdir -p "$FOAM_USER_APPBIN"
    (cd "$src" && wmake > "$OUT/log.build-$1" 2>&1) && echo "$1 built" || { echo "$1 BUILD FAILED"; grep -n -E "error" "$OUT/log.build-$1" | head -20 | cut -c1-200; }
}
stage() { # stage CASE MODULE
    local c=$OUT/case-$1 fork=$OUT/src-fork/Solver_Examples/PODFoam
    if [[ $KIND == stabilised ]]; then
        local s=$OUT/stage-$1; mkdir -p "$s"
        WM_PROJECT_VERSION=$WM_PROJECT_VERSION $PY "$fork/validation/prepare_case.py" "$fork" "$s"
        cp -r "$s/fixed-pod" "$c"; rm -rf "$s"
        sed -i '/^podSvdInterval/d; s/^endTime .*/endTime 2e-5;/; s/^writeInterval .*/writeInterval 20;/' "$c/system/controlDict"
    else
        mkdir -p "$c"
        cp -rL "$fork/Run_Case/0" "$fork/Run_Case/constant" "$fork/Run_Case/system" "$c/"
        rm -f "$c/0/uniform/time"
        sed -i 's/^endTime .*/endTime 1.5e-4;/; s/^startFrom .*/startFrom startTime;/; s/^writePrecision .*/writePrecision 12;/' "$c/system/controlDict"
        if [[ $VER == v* ]]; then sed -i '/^LES/,/^}/ s/^{/{\n    LESModel Smagorinsky;/' "$c/constant/turbulenceProperties"; fi
    fi
    cp "$OUT/$2" "$c/python_module.py"
    blockMesh -case "$c" > "$c/log.blockMesh" 2>&1
}
run() { # run CASE BUILD
    local c=$OUT/case-$1 status=0
    (cd "$c" && env MPLCONFIGDIR=$c/mpl "$OUT/bin-$2/PODFoam" -case "$c" > log.PODFoam 2>&1) || status=$?
    printf '%s\n' "$status" > "$c/exit-status"; echo "$1 exit $status steps $(grep -c '^Courant Number mean' "$c/log.PODFoam")"
}
build upstream; build fork
stage upstream module-recording.py; run upstream upstream
stage fork module-recording.py; run fork fork
stage fork-overwrite module-overwrite.py; run fork-overwrite fork
if [[ $VER == v* ]]; then
    build fork-plainp
    stage fork-plainp module-overwrite.py; run fork-plainp fork-plainp
fi
