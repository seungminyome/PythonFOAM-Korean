#!/usr/bin/env bash
# Start llama-server with Gemma 4 12B QAT Q4_0 + projector on the GPU of this
# node, write server.pid into POD_LLM_RUNTIME and wait until /health is ok.
# Flags mirror the E2B runs (context 2048, one slot, 256 image tokens
# requested, reasoning off); the only changes are all layers on the GPU and the
# projector offloaded as well. With the 12B projector the server caps image
# tokens at 128 because --ubatch-size is 128.
# picture_test.slurm sets LLM_MODEL_FILE, LLM_PROJECTOR_FILE, LLM_CTX, LLM_BATCH
# and LLM_UBATCH for other models and a larger context, and POD_LLM_STATE for
# its own pid, log and port files; unset, nothing changes.
set -euo pipefail
runtime_dir="${POD_LLM_RUNTIME:?set POD_LLM_RUNTIME}"
state="${POD_LLM_STATE:-$runtime_dir}"
mkdir -p "$state"
port="${POD_LLM_PORT:-8088}"
alias="${LLM_MODEL:-gemma-4-12b-it-qat-q4_0-vision}"
tag=b11429
bindir="$runtime_dir/llama-$tag-cuda"
model="${LLM_MODEL_FILE:-$runtime_dir/gemma-4-12b-it-qat-q4_0.gguf}"
projector="${LLM_PROJECTOR_FILE:-$runtime_dir/mmproj-gemma-4-12b-it-qat-q4_0.gguf}"
[[ -f $model && -f $projector ]] || { echo "missing $model or $projector" >&2; exit 1; }
[[ -x $bindir/llama-server ]] || { echo "run setup_12b.sh first" >&2; exit 1; }
export LD_LIBRARY_PATH="$bindir:${LD_LIBRARY_PATH:-}"
if [[ -f $state/server.pid ]] && kill -0 "$(cat "$state/server.pid")" 2>/dev/null; then
    echo "server already running, pid $(cat "$state/server.pid")"; exit 0
fi
stamp=$(date -u +%Y%m%dT%H%M%SZ)
command=("$bindir/llama-server"
    --model "$model" --mmproj "$projector" --alias "$alias"
    --host 127.0.0.1 --port "$port" --ctx-size "${LLM_CTX:-2048}" --parallel 1
    --threads "${LLM_THREADS:-4}" --threads-batch "${LLM_THREADS:-4}"
    --batch-size "${LLM_BATCH:-128}" --ubatch-size "${LLM_UBATCH:-128}" --n-gpu-layers "${LLM_GPU_LAYERS:-99}"
    --image-max-tokens 256 --mtmd-batch-max-tokens 256
    --reasoning off --reasoning-budget 0 --chat-template-kwargs '{"enable_thinking":false}'
    --no-webui --metrics --log-timestamps)
printf '%q ' "${command[@]}" > "$state/server-$stamp.cmd"
"${command[@]}" > "$state/server-$stamp.log" 2>&1 &
echo $! > "$state/server.pid"
echo "$stamp" > "$state/server.stamp"
for _ in $(seq 1 120); do
    if curl -s -m 2 "http://127.0.0.1:$port/health" | grep -q '"ok"'; then
        curl -s "http://127.0.0.1:$port/v1/models" > "$state/models-$stamp.json"
        command -v nvidia-smi > /dev/null && nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv > "$state/gpu-$stamp.txt" || true
        echo "server ok on port $port, pid $(cat "$state/server.pid"), log server-$stamp.log"
        exit 0
    fi
    kill -0 "$(cat "$state/server.pid")" 2>/dev/null || { echo "server exited; see $state/server-$stamp.log" >&2; exit 1; }
    sleep 5
done
echo "server did not become healthy in 600 s" >&2; exit 1
