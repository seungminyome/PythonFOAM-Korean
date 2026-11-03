#!/bin/bash
# Runs inside the OpenFOAM image. Builds one sibling solver from upstream 6fde869 and runs its shipped case
# twice: with module-recording.py (shipped module + snapshot save) and module-copy.py (+ Python-side copy).
# Arguments: OUT SOLVER VER RC
OUT=$1 SOLVER=$2 VER=$3 RC=$4
S=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/siblings
set --    # the openfoam.com bashrc reads the positional parameters
source "$RC" >/dev/null 2>&1 || true
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH
export PYTHON_INCLUDE_PATH=$($PY -c 'import sysconfig; print(sysconfig.get_path("include"))')
export NUMPY_INCLUDE_PATH=$($PY -c 'import numpy; print(numpy.get_include())')
export PYTHON_LIB_PATH=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
export PYTHON_LIB_NAME=lpython$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LDVERSION"))')
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
case $VER in 8) DEPS=$S/pydeps/of8;; *) DEPS=$S/pydeps/$VER;; esac
export PYTHONPATH=$DEPS:$S/pydeps/tf
export MPLBACKEND=Agg MPLCONFIGDIR=$OUT/mpl TF_CPP_MIN_LOG_LEVEL=1
echo "WM_PROJECT_VERSION=$WM_PROJECT_VERSION"; $PY -c 'import numpy, sys; print("python", sys.version.split()[0], "numpy", numpy.__version__)'

SRC=$OUT/src/Solver_Examples/$SOLVER
export FOAM_USER_APPBIN=$OUT/bin FOAM_MODULE_APPBIN=$OUT/bin; mkdir -p "$FOAM_USER_APPBIN"
(cd "$SRC" && wmake > "$OUT/log.build" 2>&1) && echo "BUILD ok" || { echo "BUILD FAILED"; grep -n -iE "error" "$OUT/log.build" | head -20 | cut -c1-240; exit 3; }
ls -la "$OUT/bin/$SOLVER" | awk '{print "binary", $5, $9}'

case $SOLVER in
  PODFoam_Debug) CASESRC=$SRC;;
  *) CASESRC=$SRC/Run_Case;;
esac

stage() { # stage NAME MODULE
    local c=$OUT/case-$1; mkdir -p "$c"
    cp -rL "$CASESRC/0" "$CASESRC/constant" "$CASESRC/system" "$c/"
    rm -f "$c/0/uniform/time"
    sed -i 's/^endTime .*/endTime 1.5e-4;/; s/^startFrom .*/startFrom startTime;/; s/^writePrecision .*/writePrecision 12;/' "$c/system/controlDict"
    if [[ $SOLVER == APMOSFoam ]]; then sed -i 's/^writeInterval .*/writeInterval 100;/' "$c/system/controlDict"; fi
    if [[ $VER == v* ]]; then sed -i '/^LES/,/^}/ s/^{/{\n    LESModel Smagorinsky;/' "$c/constant/turbulenceProperties"; fi
    cp "$S/modules/$SOLVER/$2" "$c/python_module.py"
    blockMesh -case "$c" > "$c/log.blockMesh" 2>&1 || echo "blockMesh failed for $1"
}
run() { # run NAME
    local c=$OUT/case-$1 status=0
    if [[ $SOLVER == APMOSFoam ]]; then
        # shipped run_case.sh: decomposePar; mpirun -np 4 APMOSFoam -parallel (inside the image's Open MPI)
        decomposePar -case "$c" > "$c/log.decomposePar" 2>&1 || echo "decomposePar failed"
        (cd "$c" && env $(env | grep -o '^SLURM[^=]*' | sed 's/^/-u /') OMPI_MCA_btl=self,vader OMPI_MCA_plm_rsh_agent=/bin/false \
            mpirun --oversubscribe -np 4 "$OUT/bin/$SOLVER" -parallel > log.$SOLVER 2>&1) || status=$?
    else
        (cd "$c" && "$OUT/bin/$SOLVER" > log.$SOLVER 2>&1) || status=$?
    fi
    printf '%s\n' "$status" > "$c/exit-status"
    echo "$1 exit $status steps $(grep -c '^Courant Number mean' "$c/log.$SOLVER") snapshots $(ls "$c" | grep -c '^snapshots-')"
}
stage recording module-recording.py; run recording
stage copy module-copy.py; run copy
