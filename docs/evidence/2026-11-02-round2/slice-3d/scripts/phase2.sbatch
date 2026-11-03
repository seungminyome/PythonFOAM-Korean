#!/bin/bash
#SBATCH --job-name=r2-slice3d-gpu
#SBATCH --account=me5475
#SBATCH --partition=non-investor-gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|a6000|a30
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
# Phase 2: llama-server with Gemma 4 12B on the node's GPU (hpc/start_server.sh, the settings of the 2026-10-30
# GPU jobs), then the prepared requests of the test set. Argument 1: the phase-1 run folder.
set -uo pipefail
G=/cluster/medbow/gscratch/syome/github_repos; S=$G/pod-versions-20261030/r2/slice-3d
P1=${1:?phase-1 run folder}
job=${SLURM_JOB_ID:?}; RUN=$S/phase2-$job; mkdir -p "$RUN"
hpc=$S/wt/Solver_Examples/PODFoam/llm_demo/hpc
export POD_LLM_RUNTIME=$G/PythonFOAM/llm-runtime-12b POD_LLM_STATE=$RUN/server POD_LLM_PORT=$((20000 + job % 10000))
export LLM_MODEL=gemma-4-12b-it-qat-q4_0-vision LLM_CTX=4096 LLM_BATCH=512 LLM_UBATCH=512
stop() { bash "$hpc/stop_server.sh" || true; }
trap stop EXIT
trap 'echo "signal TERM"; exit 143' TERM
hostname | tee "$RUN/node.txt"; date -u +%FT%TZ > "$RUN/start.txt"
git -C "$S/wt" rev-parse HEAD > "$RUN/HEAD"; git -C "$S/wt" status --short > "$RUN/git-status.txt"
nvidia-smi -L | tee "$RUN/gpu.txt"; nvidia-smi > "$RUN/nvidia-smi.txt" 2>&1
sha256sum "$POD_LLM_RUNTIME/gemma-4-12b-it-qat-q4_0.gguf" "$POD_LLM_RUNTIME/mmproj-gemma-4-12b-it-qat-q4_0.gguf" > "$RUN/model-sha256.txt"
( module load arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0; bash "$hpc/start_server.sh" ); s=$?
echo "start_server exit $s"
[[ $s == 0 ]] || { tail -20 "$POD_LLM_STATE"/server-*.log; exit 1; }
/gscratch/syome/conda/s4f/bin/python3 -I "$S/scripts/send_requests.py" --wt "$S/wt" --test-set "$P1/testset" --output "$RUN/results" \
    --endpoint "http://127.0.0.1:$POD_LLM_PORT/v1/chat/completions" --model "$LLM_MODEL" \
    --server-note "$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1); llama.cpp b11429; ctx $LLM_CTX batch $LLM_BATCH ubatch $LLM_UBATCH image tokens 256" 2>&1 | tee "$RUN/send.out"
echo "send exit ${PIPESTATUS[0]}"
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader > "$RUN/gpu-after.txt"
date -u +%FT%TZ > "$RUN/end.txt"
