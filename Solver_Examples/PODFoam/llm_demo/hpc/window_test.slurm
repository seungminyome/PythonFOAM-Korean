#!/bin/bash
# Random-window picture test (window_test.py) on one GPU: each model in MODELS answers
# the prepared flow-window-v1 and -v2 requests of the test set in PICTURE_TEST_SET (saved
# PODFoam states, each drawn with the plotted window placed at random around the fastest
# cell). Same server settings as picture_test.slurm; LLM_IMAGE_TOKENS and LLM_CTX can be
# raised to test the image-token cap. No OpenFOAM.
# Submit from the package root:  sbatch PODFoam/llm_demo/hpc/window_test.slurm
#SBATCH --job-name=pod-window-test
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=06:00:00
#SBATCH --output=pod-window-test-%j.out
set -euo pipefail
# --- site settings: edit these lines -------------------------------------
# MedicineBow (UWyo), as for job 24696203 (hpc/README.md):
#   module load arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0
#   export PATH=<python 3 with numpy>/bin:$PATH
# Account and partition go on the command line: sbatch --account=... --partition=...
# -------------------------------------------------------------------------
root="${SLURM_SUBMIT_DIR:-$PWD}"
pod="${POD_SOURCE:-$root/PODFoam}"                       # tarball layout
[[ -d $pod ]] || pod="$root/Solver_Examples/PODFoam"      # git clone layout
demo="$pod/llm_demo"
hpc="$demo/hpc"
job="${SLURM_JOB_ID:-local}"
export POD_LLM_RUNTIME="${POD_LLM_RUNTIME:-$root/llm-runtime-12b}"
out="$root/results/window-test-$job"
# this job's own server files and port, so two jobs on one node or one runtime
# folder do not use or stop each other's server
export POD_LLM_STATE="$out/server"
export POD_LLM_PORT="${POD_LLM_PORT:-$((20000 + ${SLURM_JOB_ID:-0} % 10000))}"
endpoint="http://127.0.0.1:$POD_LLM_PORT/v1/chat/completions"
tests="${PICTURE_TEST_SET:-$root/picture-window-test-20261022}"
models="${MODELS:-e2b e2b-bf16 e2b-qat e4b 12b 26b 31b}"
bindir="$POD_LLM_RUNTIME/llama-b11429-cuda"
python3 -c 'import numpy' || { echo "numpy missing: module load python or pip install numpy" >&2; exit 1; }
[[ -f $tests/manifest.json ]] || { echo "no test set at $tests (PICTURE_TEST_SET)" >&2; exit 1; }
[[ -x $bindir/llama-server ]] || { echo "no llama-server in $bindir; see hpc/README.md" >&2; exit 1; }
mkdir -p "$out" "$POD_LLM_STATE"
# every request file and the answer key must match the manifest before any GPU time is spent
(cd "$demo" && python3 window_test.py check --test-set "$tests") || { echo "test set damaged or incomplete; recopy it" >&2; exit 1; }
export FETCHED_LIST="$out/fetched.txt"
bash "$hpc/fetch_models.sh" $models
nvidia-smi > "$out/nvidia-smi.txt" 2>&1 || true
(module list) > "$out/modules.txt" 2>&1 || true
LD_LIBRARY_PATH="$bindir:${LD_LIBRARY_PATH:-}" "$bindir/llama-server" --version > "$out/llama-server-version.txt" 2>&1 || true
{ find "$bindir" -maxdepth 1 -type f -exec sha256sum {} +
  sha256sum "$tests/manifest.json" "$tests/truth.private.json" "$demo"/*.py "$hpc"/*; } > "$out/sha256.txt"
trap 'bash "$hpc/stop_server.sh" || true' EXIT
gpu=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || true)
for key in $models; do
    IFS=$'\t' read -r _ alias repo revision weights _ projector _ folder < <(awk -F'\t' -v k="$key" '$1 == k' "$hpc/models.tsv")
    export LLM_MODEL="$alias" LLM_CTX="${LLM_CTX:-4096}" LLM_BATCH=512 LLM_UBATCH=512 LLM_IMAGE_TOKENS="${LLM_IMAGE_TOKENS:-256}"
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
    note="$repo@$revision $weights + $projector; llama.cpp b11429 CUDA (llama-server-version.txt); $gpu; all layers on GPU; context $LLM_CTX, batch 512, ubatch 512, image token limit $LLM_IMAGE_TOKENS, parallel 1, temperature 0"
    (cd "$demo" && python3 window_test.py run --test-set "$tests" --model "$alias" --endpoint "$endpoint" \
        --server-note "$note" --output "$out/$key") || echo "$key: run exited with an error or failed requests (see the .out file)" | tee -a "$out/failed.txt"
    cp "$POD_LLM_STATE/server-$stamp.log" "$out/server-$key.log"
    cp "$POD_LLM_STATE/server-$stamp.cmd" "$out/server-$key.cmd"
    cp "$POD_LLM_STATE/models-$stamp.json" "$out/models-$key.json" 2>/dev/null || true
    cp "$POD_LLM_STATE/gpu-$stamp.txt" "$out/gpu-$key.txt" 2>/dev/null || true
    bash "$hpc/stop_server.sh"
done
runs=()
for key in $models; do [[ -f $out/$key/run.json ]] && runs+=("$out/$key"); done
if (( ${#runs[@]} )); then
    (cd "$demo" && python3 window_test.py report "${runs[@]}" --test-set "$tests" --output "$out/report.md") \
        || echo "report: some sets have no summary" | tee -a "$out/failed.txt"
fi
cp "$root/pod-window-test-$job.out" "$out/job-so-far.out" 2>/dev/null || true
tar -czf "$out.tar.gz" -C "$(dirname "$out")" "$(basename "$out")"
(cd "$(dirname "$out")" && sha256sum "$(basename "$out").tar.gz" > "$(basename "$out").tar.gz.sha256")
echo "done: $out.tar.gz"
# Optional: put the results on the temporary GitHub release named by RESULTS_RELEASE.
# Needs GH_TOKEN with write access to the repository's contents (README.ko.md).
if [[ -n ${GH_TOKEN:-} && -n ${RESULTS_RELEASE:-} ]]; then
    set +e
    slug="${RESULTS_REPO:-seungminyome/PythonFOAM}"
    id=$(curl -s -H "Authorization: Bearer $GH_TOKEN" "https://api.github.com/repos/$slug/releases/tags/$RESULTS_RELEASE" \
         | python3 -c 'import json, sys; print(json.load(sys.stdin)["id"])' 2>/dev/null)
    for file in "$out.tar.gz" "$out.tar.gz.sha256"; do
        if [[ -n $id ]] && curl --fail -s -o /dev/null -X POST -H "Authorization: Bearer $GH_TOKEN" \
               -H "Content-Type: application/octet-stream" --upload-file "$file" \
               "https://uploads.github.com/repos/$slug/releases/$id/assets?name=$(basename "$file")"; then
            echo "uploaded $(basename "$file") to $slug release $RESULTS_RELEASE"
        else
            echo "upload of $(basename "$file") failed; copy it by hand"
        fi
    done
    set -e
fi
# Optional cleanup. CLEANUP_MODELS=1 deletes the files this job downloaded (fetched.txt);
# CLEANUP_MODELS=all deletes the models/<key> folders of every key in MODELS, also files
# that were there before. The 12B files of 2026-10-19 ('.') are never deleted. Do not use
# either while another job uses the same POD_LLM_RUNTIME.
if [[ ${CLEANUP_MODELS:-0} == 1 && -f $FETCHED_LIST ]]; then
    while read -r file; do
        [[ $file == "$POD_LLM_RUNTIME"/models/* ]] && rm -f "$file" && echo "removed $file"
    done < "$FETCHED_LIST"
    find "$POD_LLM_RUNTIME/models" -mindepth 1 -type d -empty -delete 2>/dev/null || true
elif [[ ${CLEANUP_MODELS:-0} == all ]]; then
    for key in $models; do
        folder=$(awk -F'\t' -v k="$key" '$1 == k {print $9}' "$hpc/models.tsv")
        if [[ $folder == models/* && -d $POD_LLM_RUNTIME/$folder ]]; then
            rm -rf "${POD_LLM_RUNTIME:?}/$folder" && echo "removed $folder"
        fi
    done
fi
