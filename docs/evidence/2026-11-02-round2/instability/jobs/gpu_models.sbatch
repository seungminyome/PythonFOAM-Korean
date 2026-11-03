#!/bin/bash
#SBATCH --job-name=inst2-gpu
#SBATCH --account=me5475
#SBATCH --partition=non-investor-gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint='l40s|a6000'
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:30:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/instability
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/instability/logs/gpu-%j.out
# Gemma 4 12B and 31B (QAT Q4_0) on the three sets of the 2026-11-01 instability test: the
# server settings of job 24929533 (hpc/window_test.slurm), one model after the other.
set -uo pipefail
R=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/instability
G=/cluster/medbow/gscratch/syome/github_repos
REPO=$R/wt
demo=$REPO/Solver_Examples/PODFoam/llm_demo
hpc=$demo/hpc
job=${SLURM_JOB_ID:?}
out=$R/results/gpu-$job; mkdir -p "$out"
tests=$R/test-set
export PATH=/gscratch/syome/conda/s4f/bin:$PATH
export POD_LLM_RUNTIME=$G/PythonFOAM/llm-runtime-12b
export POD_LLM_STATE=$out/server
export POD_LLM_PORT=$((20000 + job % 10000))
endpoint="http://127.0.0.1:$POD_LLM_PORT/v1/chat/completions"
bindir=$POD_LLM_RUNTIME/llama-b11429-cuda
models="${MODELS:-12b 31b}"
module load arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0
hostname | tee "$out/node.txt"; date -u +%FT%TZ
git -C "$REPO" rev-parse HEAD | tee "$out/HEAD"; git -C "$REPO" status --short > "$out/git-status.txt"
nvidia-smi > "$out/nvidia-smi.txt" 2>&1 || true
(module list) > "$out/modules.txt" 2>&1 || true
LD_LIBRARY_PATH="$bindir:${LD_LIBRARY_PATH:-}" "$bindir/llama-server" --version > "$out/llama-server-version.txt" 2>&1 || true
(cd "$demo" && python3 instability_test2.py check --test-set "$tests") || { echo "test set damaged" >&2; exit 1; }
{ find "$bindir" -maxdepth 1 -type f -exec sha256sum {} +
  sha256sum "$tests/manifest.json" "$tests/truth.private.json" "$demo"/*.py "$hpc"/*; } > "$out/sha256.txt"
# model files present with the right hash (no download: fetch_models.sh only checks files that exist)
for key in $models; do
    IFS=$'\t' read -r _ alias repo revision weights wsha projector psha folder < <(awk -F'\t' -v k="$key" '$1 == k' "$hpc/models.tsv")
    for pair in "$weights $wsha" "$projector $psha"; do
        set -- $pair; f="$POD_LLM_RUNTIME/$folder/$1"
        [[ -f $f ]] || { echo "missing $f" | tee -a "$out/failed.txt"; exit 1; }
        echo "$2  $f" | sha256sum --check --status && echo "ok $f" || { echo "hash mismatch $f" | tee -a "$out/failed.txt"; exit 1; }
    done
done
trap 'bash "$hpc/stop_server.sh" || true' EXIT
gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || true)
for key in $models; do
    IFS=$'\t' read -r _ alias repo revision weights _ projector _ folder < <(awk -F'\t' -v k="$key" '$1 == k' "$hpc/models.tsv")
    export LLM_MODEL="$alias" LLM_CTX=4096 LLM_BATCH=512 LLM_UBATCH=512 LLM_IMAGE_TOKENS=256
    export LLM_MODEL_FILE="$POD_LLM_RUNTIME/$folder/$weights" LLM_PROJECTOR_FILE="$POD_LLM_RUNTIME/$folder/$projector"
    echo "=== $key ($alias) $(date -u +%FT%TZ)"
    rm -f "$POD_LLM_STATE/server.stamp"
    if ! bash "$hpc/start_server.sh"; then
        echo "$key: server did not start" | tee -a "$out/failed.txt"
        stamp=$(cat "$POD_LLM_STATE/server.stamp" 2>/dev/null || true)
        [[ -n $stamp ]] && cp "$POD_LLM_STATE/server-$stamp.log" "$out/server-$key.log" 2>/dev/null || true
        bash "$hpc/stop_server.sh" || true
        continue
    fi
    stamp=$(cat "$POD_LLM_STATE/server.stamp")
    if ! curl -s "http://127.0.0.1:$POD_LLM_PORT/v1/models" | grep -q "\"$alias\""; then
        echo "$key: the server on port $POD_LLM_PORT is not $alias" | tee -a "$out/failed.txt"
        bash "$hpc/stop_server.sh" || true
        continue
    fi
    note="$repo@$revision $weights + $projector; llama.cpp b11429 CUDA (llama-server-version.txt); $gpu; all layers on GPU; context 4096, batch 512, ubatch 512, image token limit 256, parallel 1, temperature 0"
    (cd "$demo" && python3 instability_test2.py run --test-set "$tests" --model "$alias" --endpoint "$endpoint" \
        --server-note "$note" --output "$out/$key") || echo "$key: run exited with an error or failed requests" | tee -a "$out/failed.txt"
    cp "$POD_LLM_STATE/server-$stamp.log" "$out/server-$key.log"
    cp "$POD_LLM_STATE/server-$stamp.cmd" "$out/server-$key.cmd"
    cp "$POD_LLM_STATE/models-$stamp.json" "$out/models-$key.json" 2>/dev/null || true
    cp "$POD_LLM_STATE/gpu-$stamp.txt" "$out/gpu-$key.txt" 2>/dev/null || true
    bash "$hpc/stop_server.sh"
done
runs=()
for key in $models; do [[ -f $out/$key/run.json ]] && runs+=("$out/$key"); done
if (( ${#runs[@]} )); then
    (cd "$demo" && python3 instability_test2.py report "${runs[@]}" --test-set "$tests" \
        --oct28 "$REPO/docs/evidence/2026-10-28-instability/results/window-test-24929533" --output "$out/report.md") \
        || echo "report failed" | tee -a "$out/failed.txt"
fi
sacct -j "$job" -o JobID,Start,End,Elapsed,NodeList,State -P > "$out/sacct.txt" 2>/dev/null || true
date -u +%FT%TZ; echo done
