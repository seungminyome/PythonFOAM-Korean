#!/bin/bash
# Inside upstream's image romitmaulik1/pythonfoam_docker (Ubuntu 18.04, OpenFOAM 8, Python 3.6.9).
OUT=$1
source /opt/openfoam8/etc/bashrc > /dev/null 2>&1
python3 --version; g++ --version | head -1
export POD_WORKSPACE=$OUT/ws; mkdir -p "$POD_WORKSPACE"
export TMPDIR=$OUT/tmp; mkdir -p "$TMPDIR"
cd "$OUT/PF/Solver_Examples/PODFoam" || exit 1
echo "=== validation: only an OpenFOAM sourced, no variable set"
./validation/run_v2106.sh > "$OUT/validation.log" 2>&1; echo "validation exit $?"; tail -1 "$OUT/validation.log" | cut -c1-200
echo "=== wclean && wmake as in the top-level README"
export PYTHON_LIB_PATH=$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
export PYTHON_INCLUDE_PATH=$(python3 -c 'import sysconfig; print(sysconfig.get_path("include"))')
export NUMPY_INCLUDE_PATH=$(python3 -c 'import numpy; print(numpy.get_include())')
export PYTHON_LIB_NAME=lpython3.6m
export FOAM_USER_APPBIN=$OUT/bin; mkdir -p "$FOAM_USER_APPBIN"
(wclean && wmake) > "$OUT/log.wmake" 2>&1; echo "wmake exit $?"; tail -1 "$OUT/log.wmake" | cut -c1-120
wclean > /dev/null 2>&1
echo "=== shipped Run_Case with upstream's python_module.py, 120 s"
cp -r Run_Case "$OUT/run"; cd "$OUT/run"; blockMesh > log.blockMesh 2>&1
timeout 120 "$OUT/bin/PODFoam" > log.PODFoam 2>&1; echo "PODFoam exit $? (124 = stopped by the timeout)"
for line in 'Numpy array cast time' 'Snapshot collection wall time' 'SVD Computation wall time' 'Data copy back to OF wall time' 'PDE Compute wall time' 'IO wall time' 'POD snapshot accepted' 'POD SVD returned'; do printf '%s: %s\n' "$line" "$(grep -c "$line" log.PODFoam)"; done
grep -n 'FOAM FATAL\|Traceback' log.PODFoam | head -3
