#!/bin/bash
# Paired replay (numbers only vs numbers + image, three pairs) of one saved
# PODFoam state against Gemma 4 12B on a GPU node. No OpenFOAM needed.
# Submit from the package root:  sbatch PODFoam/llm_demo/hpc/replay_12b.slurm
#SBATCH --job-name=pod-12b-replay
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=pod-12b-replay-%j.out
set -euo pipefail
# --- site settings: edit these lines -------------------------------------
# module load cuda/12.8 python/3.10
# module load <modules>    # what the source-built llama-server needs (hpc/README.md)
# export PATH=<python 3 with numpy>/bin:$PATH
# Account and partition go on the command line: sbatch --account=... --partition=...
export HF_TOKEN="${HF_TOKEN:-}"   # needed only to download the weights
# -------------------------------------------------------------------------
root="${SLURM_SUBMIT_DIR:-$PWD}"
pod="${POD_SOURCE:-$root/PODFoam}"                       # tarball layout
[[ -d $pod ]] || pod="$root/Solver_Examples/PODFoam"      # git clone layout
hpc="$pod/llm_demo/hpc"
export POD_LLM_RUNTIME="${POD_LLM_RUNTIME:-$root/llm-runtime-12b}"
export POD_LLM_PORT="${POD_LLM_PORT:-8088}"
export LLM_MODEL=gemma-4-12b-it-qat-q4_0-vision
export LLM_ENDPOINT="http://127.0.0.1:$POD_LLM_PORT/v1/chat/completions"
case="${POD_CASE:-$root/snapshot/fixed-pod}"
[[ -d $case ]] || case="$pod/../../docs/evidence/2026-10-17/pod-llm-demo.LRfJBN/fixed-pod"
out="$root/results/replay-12b-${SLURM_JOB_ID:-local}"
python3 -c 'import numpy' || { echo "numpy missing: module load python or pip install numpy" >&2; exit 1; }

bash "$hpc/setup_12b.sh"
bash "$hpc/start_server.sh"
trap 'bash "$hpc/stop_server.sh"' EXIT
note="google/gemma-4-12B-it-qat-q4_0-gguf (weights + projector); llama.cpp b11429 CUDA; $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1); all layers on GPU; context 2048; parallel 1; temperature 0; same prompts, seeds and snapshot as the 2026-10-17 E2B replay; manifest $POD_LLM_RUNTIME/runtime_manifest_12b.json"
cd "$pod/llm_demo"
python3 ablation_runner.py --case "$case" --output "$out" --repeats 3 --seed 20261017 \
    --timeout-s 300 --model "$LLM_MODEL" --endpoint "$LLM_ENDPOINT" --server-note "$note" --execute
cp "$POD_LLM_RUNTIME/runtime_manifest_12b.json" "$POD_LLM_RUNTIME"/gpu-*.txt "$POD_LLM_RUNTIME"/models-*.json "$out/" 2>/dev/null || true
tar -czf "$out.tar.gz" -C "$(dirname "$out")" "$(basename "$out")"
echo "done: $out.tar.gz"
