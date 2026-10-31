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
for which in upstream fork; do
    src=$OUT/src-$which/Solver_Examples/PODFoam
    export FOAM_USER_APPBIN=$OUT/bin-$which; mkdir -p "$FOAM_USER_APPBIN"
    (cd "$src" && wmake > "$OUT/log.build-$which" 2>&1) && echo "$which built" || { echo "$which BUILD FAILED"; grep -n -E "error" "$OUT/log.build-$which" | head -20 | cut -c1-200; continue; }
    c=$OUT/case-$which
    if [[ ${KIND:-shipped} == stabilised ]]; then
        # The bridge validation's stabilised copy of Run_Case (laminar, upwind, deltaT 1e-7), 200 steps, written every
        # 20, with upstream's python_module.py and the default POD schedule. Both builds use the fork's prepare_case.py.
        stage=$OUT/stage-$which; mkdir -p "$stage"
        WM_PROJECT_VERSION=$WM_PROJECT_VERSION $PY "$OUT/src-fork/Solver_Examples/PODFoam/validation/prepare_case.py" "$OUT/src-fork/Solver_Examples/PODFoam" "$stage"
        cp -r "$stage/fixed-pod" "$c"
        sed -i '/^podSvdInterval/d; s/^endTime .*/endTime 2e-5;/; s/^writeInterval .*/writeInterval 20;/' "$c/system/controlDict"
        cp "$OUT/src-upstream/Solver_Examples/PODFoam/Run_Case/python_module.py" "$c/python_module.py"
    else
    mkdir -p "$c"
    cp -rL "$src/Run_Case/0" "$src/Run_Case/constant" "$src/Run_Case/system" "$c/"
    cp "$src/Run_Case/python_module.py" "$c/"
    rm -f "$c/0/uniform/time"
    sed -i 's/^endTime .*/endTime 1.5e-4;/; s/^startFrom .*/startFrom startTime;/; s/^writePrecision .*/writePrecision 12;/' "$c/system/controlDict"
    # openfoam.com needs LESModel, which the case does not have (upstream's README lists v2106 as compiling, the case is written for openfoam.org)
    if [[ $VER == v* ]]; then sed -i 's/^LES\s*$/LES/; /^LES/,/^}/ s/^{/{\n    LESModel Smagorinsky;/' "$c/constant/turbulenceProperties"; fi
    fi
    blockMesh -case "$c" > "$c/log.blockMesh" 2>&1
    status=0
    (cd "$c" && env MPLCONFIGDIR=$c/mpl "$FOAM_USER_APPBIN/PODFoam" -case "$c" > log.PODFoam 2>&1) || status=$?
    printf '%s\n' "$status" > "$c/exit-status"; echo "$which case exit $status"
    grep -c '^Time = ' "$c/log.PODFoam"; tail -4 "$c/log.PODFoam" | cut -c1-160
done
