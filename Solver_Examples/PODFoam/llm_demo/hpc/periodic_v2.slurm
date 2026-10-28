#!/bin/bash
# A long PODFoam run with a v2 describe request every N steps (run_periodic.py) and its twin
# without requests, from the baseline staging of an earlier async_v2.slurm run; Gemma 4 12B on
# the node's GPU, the solver in the OpenFOAM v2212 Apptainer image (see async_v2.slurm).
# Submit from the repository root:
#   POD_SUITE_RUN=<pod-llm-async.XXXXXX of async_v2.slurm> sbatch --account=... --partition=... \
#       Solver_Examples/PODFoam/llm_demo/hpc/periodic_v2.slurm
#SBATCH --job-name=pod-periodic-v2
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --output=pod-periodic-v2-%j.out
set -euo pipefail
# --- site settings: edit these lines (MedicineBow, 2026-10-27) -----------------------------------
SIF=${SIF:-/cluster/medbow/gscratch/syome/s4f/of2212.sif}          # OpenFOAM v2212 image
export PYTHON=${PYTHON:-/gscratch/syome/conda/s4f/bin/python3}       # Python 3 with numpy + matplotlib
export POD_SUITE_RUN=${POD_SUITE_RUN:?a PASSed v2 run of async_v2.slurm (its async-no-llm staging and sources)}
host_modules="arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0"
# ------------------------------------------------------------------------------------------------
root="${SLURM_SUBMIT_DIR:-$PWD}"
pod="$root/Solver_Examples/PODFoam"
hpc="$pod/llm_demo/hpc"
job=${SLURM_JOB_ID:-local}
out=${POD_PERIODIC_OUT:-$root/../pod-periodic-v2/run-$job}
mkdir -p "$out"
export POD_LLM_RUNTIME=${POD_LLM_RUNTIME:-$root/llm-runtime-12b}
export POD_LLM_STATE=$out/server
export POD_LLM_PORT=${POD_LLM_PORT:-$((20000 + ${SLURM_JOB_ID:-0} % 10000))}
export LLM_MODEL=${LLM_MODEL:-gemma-4-12b-it-qat-q4_0-vision}
export LLM_ENDPOINT=http://127.0.0.1:$POD_LLM_PORT/v1/chat/completions
export LLM_CTX=${LLM_CTX:-4096} LLM_BATCH=512 LLM_UBATCH=512
export LLM_TIMEOUT_S=120 LLM_KILL_JOIN_S=${LLM_KILL_JOIN_S:-0.2}
export OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc PYTHONDONTWRITEBYTECODE=1
export LLM_IMAGE_XRANGE=${LLM_IMAGE_XRANGE:-0,0.12} LLM_IMAGE_YRANGE=${LLM_IMAGE_YRANGE:-0,0.04}
PERIODIC_STEPS=${PERIODIC_STEPS:-24000} PERIODIC_FIRST=${PERIODIC_FIRST:-250} PERIODIC_EVERY=${PERIODIC_EVERY:-250}
PERIODIC_MAX_PENDING=${PERIODIC_MAX_PENDING:-1} PERIODIC_WRITE=${PERIODIC_WRITE:-250}
# the code that runs, recorded on the host
export POD_GIT_RECORDS=$out/git
mkdir -p "$POD_GIT_RECORDS"
git -C "$root" rev-parse HEAD > "$POD_GIT_RECORDS/HEAD"
git -C "$root" status --short > "$POD_GIT_RECORDS/git-status.txt"
git -C "$root" diff --binary > "$POD_GIT_RECORDS/changes.patch"
# the solver binary of the suite run (built in the image against this Python) and its callback
# sources are reused: the periodic case must run the code the suite's baseline ran
exe=$(dirname "$POD_SUITE_RUN")/llm-demo-work/bin/PODFoam
[[ -x $exe ]] || { echo "no PODFoam next to $POD_SUITE_RUN" >&2; exit 1; }
# the callback module of this checkout is the one with LLM_ANALYSIS_EVERY; copy it over the
# frozen sources into a folder of this run, so the records say what ran
frozen="$out/executed-callback-source"
cp -r "$POD_SUITE_RUN/executed-callback-source" "$frozen"
for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do
    cp "$pod/llm_demo/$f" "$frozen/$f"
done
sha256sum "$frozen"/* > "$out/executed-callback-source.sha256"
trap 'if [[ -n ${smi:-} ]]; then kill "$smi" 2>/dev/null || true; fi; bash "$hpc/stop_server.sh" || true' EXIT
(
    module load $host_modules
    nvidia-smi > "$out/nvidia-smi.txt" 2>&1 || true
    bash "$hpc/start_server.sh"
)
nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv -lms 1000 > "$out/gpu-samples.csv" 2>&1 &
smi=$!
module load apptainer
status=0
# a staging copy of the suite whose executed-callback-source is this run's
staged="$out/suite-staging"
mkdir -p "$staged"
ln -s "$POD_SUITE_RUN/async-no-llm" "$staged/async-no-llm"
cp "$POD_SUITE_RUN/async-settings.json" "$staged/"
ln -s "$frozen" "$staged/executed-callback-source"
apptainer exec "$SIF" bash -c '
    set +e; source "$OPENFOAM_BASHRC" > /dev/null 2>&1; set -eo pipefail
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
    "$PYTHON" "'"$pod"'/llm_demo/run_periodic.py" "'"$staged"'" "'"$exe"'" "'"$out"'/periodic" \
        --steps '"$PERIODIC_STEPS"' --first '"$PERIODIC_FIRST"' --every '"$PERIODIC_EVERY"' \
        --max-pending '"$PERIODIC_MAX_PENDING"' --write '"$PERIODIC_WRITE"' | tee "'"$out"'/periodic.log"' || status=$?
for file in "$POD_LLM_STATE"/server-*.cmd "$POD_LLM_STATE"/server-*.log "$POD_LLM_STATE"/models-*.json \
            "$POD_LLM_STATE"/gpu-*.txt "$POD_LLM_RUNTIME/runtime_manifest_12b.json"; do
    [[ -f $file ]] && cp "$file" "$out/" || true
done
echo "done: $out (exit $status)"
exit $status
