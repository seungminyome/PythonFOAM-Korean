#!/usr/bin/env bash
# Download llama.cpp b11429 (CUDA build) and Gemma 4 12B QAT Q4_0 (weights +
# image projector) into POD_LLM_RUNTIME, check the SHA-256 of the pinned files,
# and record the SHA-256 of what was fetched and of the llama-server in use.
# About 8 GB. The Gemma licence applies:
# https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf . If HF_TOKEN is set it is
# sent with the download.
set -euo pipefail
runtime_dir="${POD_LLM_RUNTIME:?set POD_LLM_RUNTIME (directory with 10 GB free)}"
cuda="${LLAMA_CUDA:-12.8}"            # 12.8 or 13.4; needs a matching driver on the GPU node
tag=b11429
repo=google/gemma-4-12B-it-qat-q4_0-gguf
pinned_revision=29d097773436b69ff9feafd636ab4cf873786537   # the commit whose files are hashed below
revision="${GEMMA_12B_REVISION:-$pinned_revision}"
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
fetch "https://github.com/ggml-org/llama.cpp/releases/download/$tag/$archive" "$archive"
fetch "https://github.com/ggml-org/llama.cpp/releases/download/$tag/$cudart" "$cudart"
# The pinned revision's files and the CUDA 12.8 archives of b11429 must have these
# SHA-256 (the size check is the fast pre-check). Another revision or CUDA build is
# hashed into sha256.txt but not checked.
expected=()
if [[ $revision == "$pinned_revision" ]]; then
    expect_bytes "$model" 6975879296
    expect_bytes "$projector" 175115616
    expected+=("93567e57a8fe10b23569b9d9ec38cd005deedf71e29477c421a4b83f418a538b  $model"
               "cb018338a7538a9814d994bfe54644c71eb7ed54e31eae2f721e45fd3c260da7  $projector")
else
    echo "GEMMA_12B_REVISION=$revision is not the pinned revision: its SHA-256 is recorded, not checked"
fi
if [[ $cuda == 12.8 ]]; then
    expected+=("b13c64b9224d3c89d9993945d70cc21177ad00178c21b8d34237e3bc139834f1  $archive"
               "f4ab593e31507320b121f2cb21791f4c72420a2483d3df8bf2ca1a97d04e6845  $cudart")
else
    echo "LLAMA_CUDA=$cuda: the archives' SHA-256 is recorded, not checked"
fi
if (( ${#expected[@]} )); then
    printf '%s\n' "${expected[@]}" | sha256sum --check
fi
if [[ ! -x llama-$tag-cuda/llama-server ]]; then
    # Archive layouts differ (top-level directory or flat), so flatten both. The
    # soname links (libllama-common.so.0 -> libllama-common.so.0.6.0 and so on)
    # must come along: without them llama-server stops with "libllama-common.so.0:
    # cannot open shared object file".
    rm -rf extract.tmp; mkdir -p extract.tmp "llama-$tag-cuda"
    tar -xzf "$archive" -C extract.tmp
    tar -xzf "$cudart" -C extract.tmp
    find extract.tmp -mindepth 1 \( -type f -o -type l \) -exec mv -t "llama-$tag-cuda/" {} +
    rm -rf extract.tmp
    chmod +x "llama-$tag-cuda"/llama-*
fi
[[ -x llama-$tag-cuda/llama-server ]] || { echo "llama-server not found after extraction" >&2; exit 1; }
# The archives are hashed even when llama-server is a source build
# (build_llama_cuda.sh), so the server binary itself is hashed as well.
sha256sum "$model" "$projector" "$archive" "$cudart" "llama-$tag-cuda/llama-server" > sha256.txt
"${PYTHON:-python3}" - "$runtime_dir" "$tag" "$cuda" "$repo" "$revision" "$model" "$projector" <<'PY'
import json, os, sys, subprocess, datetime
root, tag, cuda, repo, rev, model, proj = sys.argv[1:]
hashes = dict(line.split()[::-1] for line in open(f"{root}/sha256.txt"))
bindir = f"{root}/llama-{tag}-cuda"
env = dict(os.environ, LD_LIBRARY_PATH=bindir + ":" + os.environ.get("LD_LIBRARY_PATH", ""))
version = subprocess.run([f"{bindir}/llama-server", "--version"], capture_output=True, text=True, env=env)
runs = version.returncode == 0
if not runs:
    print(f"warning: llama-server does not run here: {(version.stdout + version.stderr).strip()}\n"
          "The prebuilt binaries need GLIBC_2.38 and GLIBCXX_3.4.32; see build_llama_cuda.sh in hpc/README.md.",
          file=sys.stderr)
json.dump({"created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "llama_cpp_tag": tag, "cuda_build": cuda, "model_repo": repo, "revision": rev,
           "model": model, "projector": proj, "sha256": hashes, "server_runs": runs,
           "server_version": (version.stdout + version.stderr).strip()},
          open(f"{root}/runtime_manifest_12b.json", "w"), indent=2)
PY
"${PYTHON:-python3}" -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))["server_runs"] else 1)' "$runtime_dir/runtime_manifest_12b.json" \
    && echo "runtime ready in $runtime_dir" || echo "files in $runtime_dir are complete, but llama-server does not run on this system"
