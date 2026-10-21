#!/usr/bin/env bash
# Fallback when the prebuilt CUDA binary does not run on the cluster (older
# glibc, different CUDA): build llama.cpp b11429 from source with CUDA.
# Needs cmake >= 3.14, a C++17 compiler and the CUDA toolkit (module load cuda).
# The final link needs libcuda.so.1. On MedicineBow a build on a GPU node with
# the toolkit's lib64/stubs in LDFLAGS worked; one on a CPU node without the
# stubs did not. libggml-cuda.so loads the toolkit's libcudart and libcublas,
# so the job that runs llama-server needs the same module.
set -euo pipefail
runtime_dir="${POD_LLM_RUNTIME:?set POD_LLM_RUNTIME}"
tag=b11429
cd -- "$runtime_dir"
[[ -d llama.cpp-src ]] || git clone --depth 1 --branch "$tag" https://github.com/ggml-org/llama.cpp llama.cpp-src
cmake -S llama.cpp-src -B llama.cpp-build -DGGML_CUDA=ON -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release \
      ${CMAKE_CUDA_ARCHITECTURES:+-DCMAKE_CUDA_ARCHITECTURES=$CMAKE_CUDA_ARCHITECTURES}
cmake --build llama.cpp-build --config Release --target llama-server -j "${BUILD_JOBS:-8}"
mkdir -p "llama-$tag-cuda"
cp llama.cpp-build/bin/llama-server "llama-$tag-cuda/"
cp llama.cpp-build/bin/*.so* "llama-$tag-cuda/" 2>/dev/null || true
"llama-$tag-cuda/llama-server" --version
echo "built llama-server into $runtime_dir/llama-$tag-cuda"
