#!/bin/bash
# Build PODFoam into a scratch directory and run the five observation cases
# against the resident llama-server. Needs a PASSed validation run
# (validation/run_v2106.sh) as the reference case; the newest one is used
# unless POD_REFERENCE_RUN is set. POD_OPENFOAM_VERSION (default: the sourced
# OpenFOAM, else v2106) is the version the bashrc must report, e.g. v2212.
set -eo pipefail
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
workspace=${POD_WORKSPACE:-$(cd -- "$source_dir/../../.." && pwd)}
# An OpenFOAM already sourced gives the version and the bashrc, unless they are set; else v2106.
# (Not named "version": the openfoam.org bashrc sets that.)
pod_version=${POD_OPENFOAM_VERSION:-${WM_PROJECT_VERSION:-v2106}}
bashrc=${OPENFOAM_BASHRC:-${WM_PROJECT_DIR:+$WM_PROJECT_DIR/etc/bashrc}}
bashrc=${bashrc:-/usr/lib/openfoam/openfoam2106/etc/bashrc}
python=${PYTHON:-$(command -v python3 || true)}
if ! "${python:-false}" -c 'import numpy' 2> /dev/null; then
    echo "Set PYTHON to a Python with numpy (now: '${python:-no python3 on PATH}')" >&2
    exit 1
fi

if [[ -z "${POD_REFERENCE_RUN:-}" ]]; then
    for candidate in $(ls -dt "$workspace"/pod-"$pod_version".* 2>/dev/null); do
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
source "$bashrc" > "$output/log.environment-setup" 2>&1
set -eu
[[ "${WM_PROJECT_VERSION:-}" == "$pod_version" ]] || {
    echo "The bashrc reports OpenFOAM version '${WM_PROJECT_VERSION:-}', not '$pod_version': set OPENFOAM_BASHRC and POD_OPENFOAM_VERSION" >&2
    exit 1
}
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
export POD_LLM_RUNTIME=${POD_LLM_RUNTIME:-$(cd -- "$source_dir/../../.." && pwd)/llm-runtime}
export LLM_IMAGE_INPUT=${LLM_IMAGE_INPUT:-1}
export LLM_TIMEOUT_S=${LLM_TIMEOUT_S:-120}
# v2 requests (LLM_IMAGE_STYLE=v2, async suite) always send 320
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
    printf 'PASS: %s\n' "$output"
else
    printf 'Cases finished, not checked (LLM_LONG_CASES): %s\n' "$output"
fi
