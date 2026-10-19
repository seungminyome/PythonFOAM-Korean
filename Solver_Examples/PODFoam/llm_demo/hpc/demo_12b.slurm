#!/bin/bash
# Five solver conditions (PODFoam, OpenFOAM v2106) with the callback talking to
# Gemma 4 12B on the same GPU node, then the paired replay of the new state.
# Needs OpenFOAM v2106 and Python 3 with numpy + matplotlib on the node.
# Submit from the package root:  sbatch PODFoam/llm_demo/hpc/demo_12b.slurm
#SBATCH --job-name=pod-12b-demo
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=03:00:00
#SBATCH --output=pod-12b-demo-%j.out
set -euo pipefail
# --- site settings: edit these lines -------------------------------------
# module load cuda/12.8 python/3.10 openfoam/2106
export OPENFOAM_BASHRC="${OPENFOAM_BASHRC:-/usr/lib/openfoam/openfoam2106/etc/bashrc}"
export HF_TOKEN="${HF_TOKEN:?export HF_TOKEN before sbatch, or set it here}"
# -------------------------------------------------------------------------
root="${SLURM_SUBMIT_DIR:-$PWD}"
pod="${POD_SOURCE:-$root/PODFoam}"
hpc="$pod/llm_demo/hpc"
export PYTHON="${PYTHON:-$(command -v python3)}"
export POD_WORKSPACE="${POD_WORKSPACE:-$root/work}"; mkdir -p "$POD_WORKSPACE"
export POD_LLM_RUNTIME="${POD_LLM_RUNTIME:-$root/llm-runtime-12b}"
export POD_LLM_PORT="${POD_LLM_PORT:-8088}"
export LLM_MODEL=gemma-4-12b-it-qat-q4_0-vision
export LLM_ENDPOINT="http://127.0.0.1:$POD_LLM_PORT/v1/chat/completions"
[[ -f $OPENFOAM_BASHRC ]] || { echo "OPENFOAM_BASHRC not found: $OPENFOAM_BASHRC" >&2; exit 1; }
"$PYTHON" -c 'import numpy, matplotlib' || { echo "numpy/matplotlib missing" >&2; exit 1; }

bash "$hpc/setup_12b.sh"
bash "$hpc/start_server.sh"
trap 'bash "$hpc/stop_server.sh"' EXIT
# 1. bridge validation (reference case, PASS required by run_demo.sh)
if ! ls -d "$POD_WORKSPACE"/pod-v2106.* > /dev/null 2>&1; then
    (cd "$pod" && ./validation/run_v2106.sh)
fi
# 2. five conditions, verification, archive
(cd "$pod" && ./llm_demo/run_demo.sh)
demo=$(ls -dt "$POD_WORKSPACE"/pod-llm-demo.* | head -1)
# 3. paired replay of the state the solver just saved
note="google/gemma-4-12B-it-qat-q4_0-gguf (weights + projector); llama.cpp b11429 CUDA; $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1); all layers on GPU; context 2048; parallel 1; temperature 0; snapshot from $demo; manifest $POD_LLM_RUNTIME/runtime_manifest_12b.json"
(cd "$pod/llm_demo" && python3 ablation_runner.py --case "$demo/fixed-pod" --output "$demo/ablation-12b" \
    --repeats 3 --seed 20261017 --timeout-s 300 --model "$LLM_MODEL" --endpoint "$LLM_ENDPOINT" --server-note "$note" --execute)
cp "$POD_LLM_RUNTIME/runtime_manifest_12b.json" "$POD_LLM_RUNTIME"/gpu-*.txt "$demo/" 2>/dev/null || true
mkdir -p "$root/results"
# run-archive.tar.gz is pack_run.py's archive (sources, records, requests,
# replies; no intermediate time steps). Everything else stays in $demo.
tar -czf "$root/results/demo-12b-${SLURM_JOB_ID:-local}.tar.gz" --ignore-failed-read -C "$demo" \
    run-archive.tar.gz demo-verification.json verification.json timings.json summary.json \
    sha256.json resident-server.json runtime_manifest_12b.json ablation-12b
echo "done: $root/results/demo-12b-${SLURM_JOB_ID:-local}.tar.gz  (full run kept in $demo)"
