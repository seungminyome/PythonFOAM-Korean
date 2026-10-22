#!/bin/bash
# Build PODFoam and run the ten-step bridge validation in a fresh directory
# under the workspace (default: the parent of the PythonFOAM checkout).
# Environment: OPENFOAM_BASHRC (v2106), PYTHON (interpreter with numpy), POD_WORKSPACE,
# POD_OPENFOAM_VERSION (default v2106; e.g. v2212 for the MedicineBow Apptainer image).
set -eo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
workspace=${POD_WORKSPACE:-$(cd -- "$source_dir/../../.." && pwd)}
python=${PYTHON:-/usr/bin/python3}
if [[ "${1:-}" == --resume && $# == 2 ]]; then
    output=$(cd -- "$2" && pwd)
    [[ -f "$output/environment.txt" && -d "$output/fixed-pod" ]]
elif [[ $# == 0 ]]; then
    output=$(mktemp -d "$workspace/pod-${POD_OPENFOAM_VERSION:-v2106}.XXXXXX")
else
    echo "Usage: $0 [--resume RUN_DIRECTORY]" >&2
    exit 2
fi
printf 'Validation directory: %s\n' "$output"
# OpenFOAM's bashrc is not errexit-safe.
set +e
source "${OPENFOAM_BASHRC:-/usr/lib/openfoam/openfoam2106/etc/bashrc}" > "$output/log.environment-setup" 2>&1
set -eu
[[ "$WM_PROJECT_VERSION" == "${POD_OPENFOAM_VERSION:-v2106}" ]]
# Keep all build products inside this run, including the executable.
export FOAM_USER_APPBIN="$output/bin"
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
unset PYTHONHOME PYTHONPATH
export PYTHON_INCLUDE_PATH=$("$python" -c 'import sysconfig; print(sysconfig.get_path("include"))')
export NUMPY_INCLUDE_PATH=$("$python" -c 'import numpy; print(numpy.get_include())')
export PYTHON_LIB_PATH=$("$python" -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
# python<LDVERSION>: also right for conda, whose LDLIBRARY names the static library
export PYTHON_LIB_NAME=lpython$("$python" -c 'import sysconfig; print(sysconfig.get_config_var("LDVERSION"))')
mkdir -p "$output/bin" "$output/build/Make"
cp -u "$source_dir/"*.H "$source_dir/PODFoam.C" "$output/build/"
cp -u "$source_dir/Make/options" "$source_dir/Make/files" "$output/build/Make/"
{
    printf 'WM_PROJECT_VERSION=%s\nWM_PROJECT_DIR=%s\nFOAM_USER_APPBIN=%s\n' "$WM_PROJECT_VERSION" "$WM_PROJECT_DIR" "$FOAM_USER_APPBIN"
    command -v pimpleFoam wmake
    "$python" -c 'import sys,numpy; print(sys.version); print("numpy",numpy.__version__)'
} > "$output/environment.txt"
if [[ -f "$output/log.build" ]]; then
    cp -p "$output/log.build" "$output/log.build.before-resume.$(date +%s)"
fi
wmake "$output/build" > "$output/log.build" 2>&1
ldd "$output/bin/PODFoam" >> "$output/environment.txt"
if grep -q 'not found' "$output/environment.txt"; then
    echo "Unresolved shared libraries; see $output/environment.txt"; exit 1
fi
if [[ ! -d "$output/fixed-pod" ]]; then
    "$python" "$source_dir/validation/prepare_case.py" "$source_dir" "$output"
fi
for case_name in baseline-pimple fixed-pimple fixed-pod; do
    if [[ ! -f "$output/$case_name/constant/polyMesh/points" ]]; then
        blockMesh -case "$output/$case_name" > "$output/$case_name/log.blockMesh" 2>&1
    fi
done
# full checkMesh report of the original mesh
if [[ ! -f "$output/log.checkMesh" ]]; then
    checkMesh -case "$output/baseline-pimple" -allGeometry -allTopology > "$output/log.checkMesh" 2>&1 || true
fi
# traps off only to reproduce the original nan
if [[ ! -f "$output/baseline-pimple/exit-status" ]]; then
    set +e
    FOAM_SIGFPE=false pimpleFoam -case "$output/baseline-pimple" > "$output/baseline-pimple/log.pimpleFoam" 2>&1
    baseline_status=$?
    set -e
    printf '%s\n' "$baseline_status" > "$output/baseline-pimple/exit-status"
fi
baseline_status=$(cat "$output/baseline-pimple/exit-status")
[[ "$baseline_status" != 0 ]]
grep -q 'Final residual = nan' "$output/baseline-pimple/log.pimpleFoam"
export FOAM_SIGFPE=true
if ! grep -q '^End$' "$output/fixed-pimple/log.pimpleFoam" 2>/dev/null; then
    pimpleFoam -case "$output/fixed-pimple" > "$output/fixed-pimple/log.pimpleFoam" 2>&1
fi
if [[ -f "$output/fixed-pod/log.PODFoam" ]]; then
    cp -p "$output/fixed-pod/log.PODFoam" "$output/fixed-pod/log.PODFoam.before-resume.$(date +%s)"
fi
cp -u "$source_dir/validation/python_module.py" "$output/fixed-pod/python_module.py"
"$output/bin/PODFoam" -case "$output/fixed-pod" > "$output/fixed-pod/log.PODFoam" 2>&1
"$python" "$source_dir/validation/verify.py" "$output" | tee "$output/verification.json"
printf 'PASS: %s\n' "$output"
