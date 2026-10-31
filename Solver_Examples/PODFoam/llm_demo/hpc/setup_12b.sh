#!/usr/bin/env bash
# Download llama.cpp b11429 (CUDA build) and Gemma 4 12B QAT Q4_0 (weights +
# image projector) into POD_LLM_RUNTIME, record SHA-256 of what was fetched
# and of the llama-server in use.
# About 8 GB. The Gemma licence applies:
# https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf . If HF_TOKEN is set it is
# sent with the download.
set -euo pipefail
runtime_dir="${POD_LLM_RUNTIME:?set POD_LLM_RUNTIME (directory with 10 GB free)}"
cuda="${LLAMA_CUDA:-12.8}"            # 12.8 or 13.4; needs a matching driver on the GPU node
tag=b11429
repo=google/gemma-4-12B-it-qat-q4_0-gguf
revision="${GEMMA_12B_REVISION:-main}"
model=gemma-4-12b-it-qat-q4_0.gguf
projector=mmproj-gemma-4-12b-it-qat-q4_0.gguf
archive=llama-$tag-bin-ubuntu-cuda-$cuda-x64.tar.gz
cudart=cudart-llama-$tag-bin-ubuntu-cuda-$cuda-x64.tar.gz

mkdir -p -- "$runtime_dir"; cd -- "$runtime_dir"
fetch() {
    local url=$1 target=$2; shift 2
    [[ -f $target ]] && return 0
    curl --fail --location --retry 3 --continue-at - "$@" "$url" --output "$target.partial"
    mv -- "$target.partial" "$target"
}
fetch_model() {
    if [[ -n ${HF_TOKEN:-} ]]; then
        # through curl's config on stdin, so the token is not on a command line
        printf 'header = "Authorization: Bearer %s"\n' "$HF_TOKEN" | fetch "$1" "$2" --config -
    else
        fetch "$1" "$2"
    fi
}
expect_bytes() {   # sizes from the Hugging Face listing
    local actual; actual=$(stat -c %s "$1")
    [[ $actual == "$2" ]] || { echo "$1: $actual bytes, expected $2" >&2; exit 1; }
}
fetch_model "https://huggingface.co/$repo/resolve/$revision/$model" "$model"
fetch_model "https://huggingface.co/$repo/resolve/$revision/$projector" "$projector"
expect_bytes "$model" 6975879296
expect_bytes "$projector" 175115616
fetch "https://github.com/ggml-org/llama.cpp/releases/download/$tag/$archive" "$archive"
fetch "https://github.com/ggml-org/llama.cpp/releases/download/$tag/$cudart" "$cudart"
if [[ ! -x llama-$tag-cuda/llama-server ]]; then
    # Archive layouts differ (top-level directory or flat), so flatten both.
    rm -rf extract.tmp; mkdir -p extract.tmp "llama-$tag-cuda"
    tar -xzf "$archive" -C extract.tmp
    tar -xzf "$cudart" -C extract.tmp
    find extract.tmp -type f -exec mv -t "llama-$tag-cuda/" {} +
    rm -rf extract.tmp
    chmod +x "llama-$tag-cuda"/llama-*
fi
[[ -x llama-$tag-cuda/llama-server ]] || { echo "llama-server not found after extraction" >&2; exit 1; }
# The archives are hashed even when llama-server is a source build
# (build_llama_cuda.sh), so the server binary itself is hashed as well.
sha256sum "$model" "$projector" "$archive" "$cudart" "llama-$tag-cuda/llama-server" > sha256.txt
"${PYTHON:-python3}" - "$runtime_dir" "$tag" "$cuda" "$repo" "$revision" "$model" "$projector" <<'PY'
import json, sys, subprocess, datetime
root, tag, cuda, repo, rev, model, proj = sys.argv[1:]
hashes = dict(line.split()[::-1] for line in open(f"{root}/sha256.txt"))
version = subprocess.run([f"{root}/llama-{tag}-cuda/llama-server", "--version"],
                         capture_output=True, text=True)
json.dump({"created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "llama_cpp_tag": tag, "cuda_build": cuda, "model_repo": repo, "revision": rev,
           "model": model, "projector": proj, "sha256": hashes,
           "server_version": (version.stdout + version.stderr).strip()},
          open(f"{root}/runtime_manifest_12b.json", "w"), indent=2)
PY
echo "runtime ready in $runtime_dir"
