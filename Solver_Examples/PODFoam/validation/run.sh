#!/bin/bash
# Build PODFoam and run the ten-step bridge validation in a fresh directory under
# the workspace (default: validation/runs/ next to this script).
# Environment: OPENFOAM_BASHRC and POD_OPENFOAM_VERSION (v2012, v2106, v2212 or, for openfoam.org,
# 8; default: the sourced OpenFOAM, else v2106), PYTHON (interpreter with numpy; default: python3
# on PATH), POD_WORKSPACE. Options: --baseline (also run the shipped case with pimpleFoam),
# --resume RUN_DIRECTORY (reuse a run directory of this script); --baseline comes first.
set -eo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
workspace=${POD_WORKSPACE:-$source_dir/validation/runs}
# An OpenFOAM already sourced gives the version and the bashrc, unless they are set; else v2106.
# (Not named "version": the openfoam.org bashrc sets that.)
pod_version=${POD_OPENFOAM_VERSION:-${WM_PROJECT_VERSION:-v2106}}
bashrc=${OPENFOAM_BASHRC:-${WM_PROJECT_DIR:+$WM_PROJECT_DIR/etc/bashrc}}
bashrc=${bashrc:-/usr/lib/openfoam/openfoam2106/etc/bashrc}
python=${PYTHON:-$(command -v python3 || true)}
# The checks and the build see the same Python: no user site-packages, no PYTHONPATH.
export PYTHONNOUSERSITE=1
unset PYTHONHOME PYTHONPATH
if ! "${python:-false}" -c 'import numpy' 2> /dev/null; then
    echo "Set PYTHON to a Python with numpy (now: '${python:-no python3 on PATH}')" >&2
    exit 1
fi
baseline=0
if [[ "${1:-}" == --baseline ]]; then
    baseline=1
    shift
fi
fresh=0
if [[ "${1:-}" == --resume && $# == 2 ]]; then
    if [[ ! -f "$2/environment.txt" || ! -d "$2/fixed-pod" ]]; then
        echo "'$2' is not a run directory of this script: no environment.txt or no fixed-pod/" >&2
        exit 1
    fi
    output=$(cd -- "$2" && pwd)
elif [[ $# == 0 ]]; then
    mkdir -p "$workspace"
    output=$(mktemp -d "$workspace/pod-$pod_version.XXXXXX")
    fresh=1
else
    echo "Usage: $0 [--baseline] [--resume RUN_DIRECTORY]   (--baseline must come first)" >&2
    exit 2
fi
printf 'Validation directory: %s\n' "$output"
# A failed step names itself and its log.
fail() { echo "$1 failed; see $2" >&2; exit 1; }
# OpenFOAM's bashrc is not errexit-safe.
set +e
source "$bashrc" > "$output/log.environment-setup" 2>&1
set -eu
[[ "${WM_PROJECT_VERSION:-}" == "$pod_version" ]] || {
    echo "The bashrc reports OpenFOAM version '${WM_PROJECT_VERSION:-}', not '$pod_version': set OPENFOAM_BASHRC and POD_OPENFOAM_VERSION" >&2
    [[ $fresh == 1 ]] && rm -rf "$output"
    exit 1
}
# Keep all build products inside this run, including the executable.
export FOAM_USER_APPBIN="$output/bin"
# Unbuffered: Python's print() output appears in log.PODFoam in step order, also if the run dies.
export PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
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
wmake "$output/build" > "$output/log.build" 2>&1 || fail wmake "$output/log.build"
ldd "$output/bin/PODFoam" >> "$output/environment.txt"
if grep -q 'not found' "$output/environment.txt"; then
    echo "Unresolved shared libraries; see $output/environment.txt"; exit 1
fi
cases=(fixed-pimple fixed-pod)
[[ $baseline == 1 ]] && cases=(baseline-pimple fixed-pimple fixed-pod)
# stage the cases not yet in the run directory (all of them in a fresh run)
missing=()
for case_name in "${cases[@]}"; do
    [[ -d "$output/$case_name" ]] || missing+=("$case_name")
done
if [[ ${#missing[@]} -gt 0 ]]; then
    "$python" "$source_dir/validation/prepare_case.py" "$source_dir" "$output" "${missing[@]}"
fi
for case_name in "${cases[@]}"; do
    if [[ ! -f "$output/$case_name/constant/polyMesh/points" ]]; then
        blockMesh -case "$output/$case_name" > "$output/$case_name/log.blockMesh" 2>&1 ||
            fail blockMesh "$output/$case_name/log.blockMesh"
    fi
done
# full checkMesh report of the mesh (the same in all three cases)
if [[ ! -f "$output/log.checkMesh" ]]; then
    checkMesh -case "$output/fixed-pimple" -allGeometry -allTopology > "$output/log.checkMesh" 2>&1 || true
fi
# --baseline: the shipped case with a fixed time step, recorded only; verify.py does not read it.
# Traps off, so that a nan shows in the log; on openfoam.org any value of FOAM_SIGFPE, also
# "false", turns them on, so there the variable is unset.
if [[ $baseline == 1 && ! -f "$output/baseline-pimple/exit-status" ]]; then
    traps_off=(env FOAM_SIGFPE=false)
    [[ "$WM_PROJECT_VERSION" == v* ]] || traps_off=(env -u FOAM_SIGFPE)
    set +e
    "${traps_off[@]}" pimpleFoam -case "$output/baseline-pimple" > "$output/baseline-pimple/log.pimpleFoam" 2>&1
    baseline_status=$?
    set -e
    printf '%s\n' "$baseline_status" > "$output/baseline-pimple/exit-status"
fi
export FOAM_SIGFPE=true
if ! grep -q '^End$' "$output/fixed-pimple/log.pimpleFoam" 2>/dev/null; then
    pimpleFoam -case "$output/fixed-pimple" > "$output/fixed-pimple/log.pimpleFoam" 2>&1 ||
        fail pimpleFoam "$output/fixed-pimple/log.pimpleFoam"
fi
if [[ -f "$output/fixed-pod/log.PODFoam" ]]; then
    cp -p "$output/fixed-pod/log.PODFoam" "$output/fixed-pod/log.PODFoam.before-resume.$(date +%s)"
fi
cp -u "$source_dir/validation/python_module.py" "$output/fixed-pod/python_module.py"
"$output/bin/PODFoam" -case "$output/fixed-pod" > "$output/fixed-pod/log.PODFoam" 2>&1 ||
    fail PODFoam "$output/fixed-pod/log.PODFoam"
"$python" "$source_dir/validation/verify.py" "$output" | tee "$output/verification.json"
printf 'PASS: %s\n' "$output"
