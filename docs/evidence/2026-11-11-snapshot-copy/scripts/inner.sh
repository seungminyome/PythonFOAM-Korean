#!/bin/bash
# Runs inside the OpenFOAM image. Arguments: OUT SOLVER VER RC CASEKIND STAGES
#   CASEKIND: shipped (endTime 1.5e-4, as round 1) | stab (fork validation's stabilised settings, dt 1e-7 fixed)
#   STAGES: space-separated list of  recording | copy | ported   (ported = minimal owned-array C++ patch + recording module)
OUT=$1 SOLVER=$2 VER=$3 RC=$4 CASEKIND=$5 STAGES=$6
S=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/siblings; N=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/small
set --
source "$RC" >/dev/null 2>&1 || true
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH
export PYTHON_INCLUDE_PATH=$($PY -c 'import sysconfig; print(sysconfig.get_path("include"))')
export NUMPY_INCLUDE_PATH=$($PY -c 'import numpy; print(numpy.get_include())')
export PYTHON_LIB_PATH=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
export PYTHON_LIB_NAME=lpython$($PY -c 'import sysconfig; print(sysconfig.get_config_var("LDVERSION"))')
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
case $VER in 8) DEPS=$S/pydeps/of8;; *) DEPS=$S/pydeps/v2106;; esac
export PYTHONPATH=$DEPS:$S/pydeps/tf
export MPLBACKEND=Agg MPLCONFIGDIR=$OUT/mpl TF_CPP_MIN_LOG_LEVEL=1
echo "WM_PROJECT_VERSION=$WM_PROJECT_VERSION"; $PY -c 'import numpy, sys; print("python", sys.version.split()[0], "numpy", numpy.__version__)'

SRC=$OUT/src/Solver_Examples/$SOLVER
case $SOLVER in PODFoam_Debug) CASESRC=$SRC;; *) CASESRC=$SRC/Run_Case;; esac

build() { # build NAME SRCDIR  -> $OUT/bin-NAME/$SOLVER
    export FOAM_USER_APPBIN=$OUT/bin-$1 FOAM_MODULE_APPBIN=$OUT/bin-$1; mkdir -p "$FOAM_USER_APPBIN"
    (cd "$2" && wmake > "$OUT/log.build-$1" 2>&1) && echo "BUILD $1 ok" || { echo "BUILD $1 FAILED"; grep -n -iE "error" "$OUT/log.build-$1" | head -20 | cut -c1-240; return 3; }
    ls -la "$OUT/bin-$1/$SOLVER" | awk '{print "binary", $5, $9}'
}
stage() { # stage NAME MODULE
    local c=$OUT/case-$1; mkdir -p "$c"
    cp -rL "$CASESRC/0" "$CASESRC/constant" "$CASESRC/system" "$c/"
    rm -f "$c/0/uniform/time"
    sed -i 's/^startFrom .*/startFrom startTime;/; s/^writePrecision .*/writePrecision 12;/' "$c/system/controlDict"
    if [[ $CASEKIND == shipped ]]; then
        sed -i 's/^endTime .*/endTime 1.5e-4;/' "$c/system/controlDict"
        if [[ $SOLVER == APMOSFoam ]]; then sed -i 's/^writeInterval .*/writeInterval 100;/' "$c/system/controlDict"; fi
        if [[ $VER == v* ]]; then sed -i '/^LES/,/^}/ s/^{/{\n    LESModel Smagorinsky;/' "$c/constant/turbulenceProperties"; fi
    else # stab: Solver_Examples/PODFoam/validation/prepare_case.py's fixed-* settings
        sed -i 's/^endTime .*/endTime 6e-6;/; s/^deltaT .*/deltaT 1e-7;/; s/^adjustTimeStep .*/adjustTimeStep no;/; s/^writeInterval .*/writeInterval 20;/' "$c/system/controlDict"
        for f in "$c/constant/momentumTransport" "$c/constant/turbulenceProperties"; do
            [[ -f $f ]] && sed -i 's/^simulationType .*/simulationType laminar;/' "$f"
        done
        sed -i 's/uniform (1e-8 0 0)/uniform (32.2 0 0)/' "$c/0/U"
        sed -i 's/default         backward;/default         Euler;/; s/div(phi,U)      Gauss linear;/div(phi,U)      Gauss upwind;/; s/Gauss linear corrected/Gauss linear limited 0.5/; s/default         corrected;/default         limited 0.5;/' "$c/system/fvSchemes"
        sed -i 's/nNonOrthogonalCorrectors 0;/nNonOrthogonalCorrectors 2;/; s/smoother        GaussSeidel;/smoother        DICGaussSeidel;/' "$c/system/fvSolution"
    fi
    echo "--- $1 controlDict:"; grep -E "^(endTime|deltaT|adjustTimeStep|writeInterval|writeControl|maxCo)" "$c/system/controlDict" | tr '\n' ' '; echo
    [[ $CASEKIND == stab ]] && { grep -h "simulationType" "$c/constant/turbulenceProperties" "$c/constant/momentumTransport" 2>/dev/null | sort -u; grep -n "internalField" "$c/0/U"; }
    cp "$N/modules/$SOLVER/$2" "$c/python_module.py"
    blockMesh -case "$c" > "$c/log.blockMesh" 2>&1 || echo "blockMesh failed for $1"
}
run() { # run NAME BIN
    local c=$OUT/case-$1 status=0 bin=$2
    if [[ $SOLVER == APMOSFoam ]]; then
        decomposePar -case "$c" > "$c/log.decomposePar" 2>&1 || echo "decomposePar failed"
        (cd "$c" && env $(env | grep -o '^SLURM[^=]*' | sed 's/^/-u /') OMPI_MCA_btl=self,vader OMPI_MCA_plm_rsh_agent=/bin/false \
            mpirun --oversubscribe -np 4 "$bin" -parallel > log.$SOLVER 2>&1) || status=$?
    else
        (cd "$c" && "$bin" > log.$SOLVER 2>&1) || status=$?
    fi
    printf '%s\n' "$status" > "$c/exit-status"
    echo "$1 exit $status steps $(grep -c '^Courant Number mean' "$c/log.$SOLVER") snapshots $(ls "$c" | grep -c '^snapshots-')"
}

for st in $STAGES; do
    case $st in
        recording|copy)
            [[ -x $OUT/bin-upstream/$SOLVER ]] || build upstream "$SRC" || continue
            stage $st module-$st.py; run $st "$OUT/bin-upstream/$SOLVER";;
        ported)
            if [[ ! -x $OUT/bin-ported/$SOLVER ]]; then
                rm -rf "$OUT/src-ported"; mkdir -p "$OUT/src-ported"; cp -r "$OUT/src/Solver_Examples" "$OUT/src-ported/"
                rm -rf "$OUT/src-ported/Solver_Examples"; cp -r "$N/branch-src/Solver_Examples" "$OUT/src-ported/"; cp "$N/branch-src/BRANCH" "$OUT/BRANCH"
                diff -u "$SRC/PythonComm.H" "$OUT/src-ported/Solver_Examples/$SOLVER/PythonComm.H" > "$OUT/ported.diff"
                build ported "$OUT/src-ported/Solver_Examples/$SOLVER" || continue
            fi
            stage ported module-recording.py; run ported "$OUT/bin-ported/$SOLVER";;
    esac
done
