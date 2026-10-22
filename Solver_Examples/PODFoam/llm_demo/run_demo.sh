#!/bin/bash
# Build PODFoam into a scratch directory and run the five observation cases
# against the resident llama-server. Needs a PASSed validation run
# (validation/run_v2106.sh) as the reference case; the newest one is used
# unless POD_REFERENCE_RUN is set. POD_OPENFOAM_VERSION (default v2106) is the
# OpenFOAM version the bashrc must report, e.g. v2212 in the MedicineBow image.
set -eo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
workspace=${POD_WORKSPACE:-$(cd -- "$source_dir/../../.." && pwd)}
python=${PYTHON:-/usr/bin/python3}

if [[ -z "${POD_REFERENCE_RUN:-}" ]]; then
    for candidate in $(ls -dt "$workspace"/pod-"${POD_OPENFOAM_VERSION:-v2106}".* 2>/dev/null); do
        if [[ -f "$candidate/verification.json" ]] \
           && grep -q '"status": "PASS"' "$candidate/verification.json"; then
            POD_REFERENCE_RUN=$candidate
            break
        fi
    done
fi
if [[ -z "${POD_REFERENCE_RUN:-}" || ! -d "$POD_REFERENCE_RUN/fixed-pod" ]]; then
    echo "No PASSed validation run found; run validation/run_v2106.sh or set POD_REFERENCE_RUN" >&2
    exit 2
fi
reference=$POD_REFERENCE_RUN
suite=${POD_SUITE:-sync}
if [[ "$suite" == async ]]; then
    output=$(mktemp -d "$workspace/pod-llm-async.XXXXXX")
else
    output=$(mktemp -d "$workspace/pod-llm-demo.XXXXXX")
fi
printf 'Reference run: %s\nDemo directory: %s\n' "$reference" "$output"

# OpenFOAM's bashrc is not errexit-safe.
set +e
source "${OPENFOAM_BASHRC:-/usr/lib/openfoam/openfoam2106/etc/bashrc}" > "$output/log.environment-setup" 2>&1
set -eu
# v2106 is the tested version; POD_OPENFOAM_VERSION=v2212 for the MedicineBow container
[[ "$WM_PROJECT_VERSION" == "${POD_OPENFOAM_VERSION:-v2106}" ]]
export PYTHONNOUSERSITE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
unset PYTHONHOME PYTHONPATH
work=$workspace/llm-demo-work
export FOAM_USER_APPBIN="$work/bin"
export PYTHON_INCLUDE_PATH=$("$python" -c 'import sysconfig; print(sysconfig.get_path("include"))')
export NUMPY_INCLUDE_PATH=$("$python" -c 'import numpy; print(numpy.get_include())')
export PYTHON_LIB_PATH=$("$python" -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')
# python<LDVERSION> (3.9, 3.11, 3.6m ...): also right for conda, whose LDLIBRARY names the static library
export PYTHON_LIB_NAME=lpython$("$python" -c 'import sysconfig; print(sysconfig.get_config_var("LDVERSION"))')
export FOAM_SIGFPE=true
mkdir -p "$work/build/Make" "$FOAM_USER_APPBIN"
cp -u "$source_dir/"*.H "$source_dir/PODFoam.C" "$work/build/"
cp -u "$source_dir/Make/options" "$source_dir/Make/files" "$work/build/Make/"
wmake "$work/build" > "$output/log.build" 2>&1
{
    printf 'WM_PROJECT_VERSION=%s\nWM_PROJECT_DIR=%s\n' "$WM_PROJECT_VERSION" "$WM_PROJECT_DIR"
    "$python" --version
    ldd "$FOAM_USER_APPBIN/PODFoam"
} > "$output/environment.txt"
if grep -q 'not found' "$output/environment.txt"; then
    echo "Unresolved shared libraries; see $output/environment.txt" >&2
    exit 1
fi

export LLM_ENDPOINT=${LLM_ENDPOINT:-http://127.0.0.1:${POD_LLM_PORT:-8088}/v1/chat/completions}
export LLM_MODEL=${LLM_MODEL:-gemma-4-E2B-it-Q4_0-vision}
export POD_LLM_RUNTIME=${POD_LLM_RUNTIME:-$workspace/llm-runtime}
export LLM_IMAGE_INPUT=${LLM_IMAGE_INPUT:-1}
export LLM_TIMEOUT_S=${LLM_TIMEOUT_S:-120}
# v2 requests (LLM_IMAGE_STYLE=v2, async suite) always send 320, as in the picture tests
default_tokens=192
[[ "$suite" == async && "${LLM_IMAGE_STYLE:-v1}" == v2 ]] && default_tokens=320
export LLM_MAX_TOKENS=${LLM_MAX_TOKENS:-$default_tokens}
if [[ "$suite" == async ]]; then
    # longer run, requests answered while the solver keeps stepping
    "$python" "$source_dir/llm_demo/run_async_cases.py" "$source_dir" "$reference" "$output" "$FOAM_USER_APPBIN/PODFoam"
    if [[ -z "${LLM_LONG_CASES:-}" ]]; then
        "$python" "$source_dir/llm_demo/verify_async.py" "$output" | tee "$output/async-verification.json"
    fi
else
    "$python" "$source_dir/llm_demo/run_cases.py" "$source_dir" "$reference" "$output" "$FOAM_USER_APPBIN/PODFoam"
    "$python" "$source_dir/validation/verify.py" "$output" > "$output/verification.json"
    "$python" "$source_dir/llm_demo/verify_demo.py" "$output" | tee "$output/demo-verification.json"
fi
if [[ -z "${LLM_LONG_CASES:-}" ]]; then
    "$python" "$source_dir/llm_demo/pack_run.py" "$output"
fi
printf 'PASS: %s\n' "$output"
