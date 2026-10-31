#!/bin/bash
# The five asynchronous cases (run_async_cases.py) with v2 pictures and Gemma 4 12B on one GPU
# node, started from a developed flow state. OpenFOAM
# runs inside an Apptainer image; llama-server runs on the host GPU and the solver's callback
# reaches it on 127.0.0.1 (the image shares the host network).
# Submit from the repository root:
#   SIF=<image> PYTHON=<python> POD_REFERENCE_RUN=<validation run> LLM_LONG_START=<time directory> \
#       sbatch --account=... --partition=... Solver_Examples/PODFoam/llm_demo/hpc/async_v2.slurm
#SBATCH --job-name=pod-async-v2
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=pod-async-v2-%j.out
set -euo pipefail
# --- site settings: from the environment ----------------------------------------------------------
SIF=${SIF:?OpenFOAM v2212 image}
export PYTHON=${PYTHON:?Python 3 with numpy + matplotlib}
export POD_REFERENCE_RUN=${POD_REFERENCE_RUN:?a PASSed validation run (validation/run_v2106.sh) on this OpenFOAM}
export LLM_LONG_START=${LLM_LONG_START:?time directory of a developed run of the same mesh, e.g. <developed case>/<time>}
# POD_HOST_MODULES="<modules>" loads what the source-built llama-server needs; empty: nothing is loaded
# OPENFOAM_BASHRC: the bashrc inside the image (default /usr/lib/openfoam/openfoam2212/etc/bashrc)
# ------------------------------------------------------------------------------------------------
root="${SLURM_SUBMIT_DIR:-$PWD}"
pod="$root/Solver_Examples/PODFoam"
hpc="$pod/llm_demo/hpc"
job=${SLURM_JOB_ID:-local}
out=${POD_ASYNC_OUT:-$root/../pod-async-v2/run-$job}                 # outside the git tree
mkdir -p "$out"
export POD_WORKSPACE=$out
# the code that runs, recorded on the host (the OpenFOAM image has no git); pack_run.py copies it
export POD_GIT_RECORDS=$out/git
mkdir -p "$POD_GIT_RECORDS"
git -C "$root" rev-parse HEAD > "$POD_GIT_RECORDS/HEAD"
git -C "$root" status --short > "$POD_GIT_RECORDS/git-status.txt"
git -C "$root" diff --binary > "$POD_GIT_RECORDS/changes.patch"
export POD_LLM_RUNTIME=${POD_LLM_RUNTIME:-$root/llm-runtime-12b}     # weights and llama-b11429-cuda
export POD_LLM_STATE=$out/server                                      # this job's pid, log and port files
export POD_LLM_PORT=${POD_LLM_PORT:-$((20000 + ${SLURM_JOB_ID:-0} % 10000))}
# the server and request settings of this job
export LLM_MODEL=${LLM_MODEL:-gemma-4-12b-it-qat-q4_0-vision}
export LLM_ENDPOINT=http://127.0.0.1:$POD_LLM_PORT/v1/chat/completions
export LLM_CTX=4096 LLM_BATCH=512 LLM_UBATCH=512
export LLM_TIMEOUT_S=120 LLM_MAX_TOKENS=320 LLM_IMAGE_STYLE=v2
export LLM_KILL_JOIN_S=${LLM_KILL_JOIN_S:-0.2}                          # a killed worker of a 0.5 GB solver took about 40 ms to reap
export POD_SUITE=async OPENFOAM_BASHRC=${OPENFOAM_BASHRC:-/usr/lib/openfoam/openfoam2212/etc/bashrc} POD_OPENFOAM_VERSION=v2212
export PYTHONDONTWRITEBYTECODE=1
# the run: 6000 steps of 5e-6 s from the start state, written every 250 steps
export LLM_LONG_STEPS=${LLM_LONG_STEPS:-6000} LLM_LONG_DT=${LLM_LONG_DT:-5e-6} LLM_LONG_WRITE=${LLM_LONG_WRITE:-250}
export LLM_LONG_STEP=${LLM_LONG_STEP:-250} LLM_LONG_SEQUENCE_STEPS=${LLM_LONG_SEQUENCE_STEPS:-3000,3250,3750}
export LLM_IMAGE_XRANGE=${LLM_IMAGE_XRANGE:-0,0.12} LLM_IMAGE_YRANGE=${LLM_IMAGE_YRANGE:-0,0.04}

trap 'if [[ -n ${smi:-} ]]; then kill "$smi" 2>/dev/null || true; fi; bash "$hpc/stop_server.sh" || true' EXIT
# the image, Python and host modules of this job
printf 'SIF=%s\nPYTHON=%s\nPOD_HOST_MODULES=%s\n' "$SIF" "$PYTHON" "${POD_HOST_MODULES:-}" > "$out/site.txt"
(
    if [[ -n ${POD_HOST_MODULES:-} ]]; then module load $POD_HOST_MODULES; fi
    (module list) >> "$out/site.txt" 2>&1 || true
    nvidia-smi > "$out/nvidia-smi.txt" 2>&1 || true
    bash "$hpc/start_server.sh"
)
nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv -lms 1000 > "$out/gpu-samples.csv" 2>&1 &
smi=$!

command -v apptainer > /dev/null || module load apptainer
suite_status=0
apptainer exec "$SIF" bash -c '
    set +e; source "$OPENFOAM_BASHRC" > /dev/null 2>&1; set -e
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH   # libpython and its libstdc++ first
    cd "'"$pod"'" && ./llm_demo/run_demo.sh' | tee "$out/suite.log" || suite_status=$?
run=$(sed -n 's/^Demo directory: //p' "$out/suite.log" | tail -1)   # the folder this job's run_demo made
if [[ -z $run || ! -f $run/async-settings.json ]]; then
    echo "done: no suite record from this job (suite exit $suite_status)"
    exit $(( suite_status ? suite_status : 1 ))
fi
for file in "$POD_LLM_STATE"/server-*.cmd "$POD_LLM_STATE"/server-*.log "$POD_LLM_STATE"/models-*.json \
            "$POD_LLM_STATE"/gpu-*.txt "$out/nvidia-smi.txt" "$out/gpu-samples.csv" "$out/site.txt" \
            "$POD_LLM_RUNTIME/runtime_manifest_12b.json"; do
    [[ -f $file ]] && cp "$file" "$run/" || true
done
echo "done: $run (suite exit $suite_status)"
exit $suite_status
