#!/bin/bash
#SBATCH --job-name=r2-setup12b
#SBATCH --account=me5475
#SBATCH --partition=non-investor-gpu
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|a6000|a30
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
# Does the runtime that setup_12b.sh just made (prebuilt CUDA build, no token) start llama-server and answer one
# request? A: as written. A2: prebuilt with soname links restored (separates the two causes). B: the README's fallback
# (build_llama_cuda.sh, then setup_12b.sh again), start_server.sh, one text request, stop.
set -uo pipefail
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030; L=$W/r2/setup12b
hpc=$L/wt/Solver_Examples/PODFoam/llm_demo/hpc
job=${SLURM_JOB_ID:?}; RUN=$L/gpu/run-$job; mkdir -p "$RUN"
export POD_LLM_RUNTIME=$L/runtime POD_LLM_STATE=$RUN/server POD_LLM_PORT=$((20000 + job % 10000))
export PYTHON=/gscratch/syome/conda/s4f/bin/python3
export LLM_MODEL=gemma-4-12b-it-qat-q4_0-vision LLM_CTX=4096 LLM_BATCH=512 LLM_UBATCH=512
unset HF_TOKEN
stop() { bash "$hpc/stop_server.sh" || true; }
trap stop EXIT
echo "node $(hostname)" | tee "$RUN/node.txt"; date -u +%FT%TZ
ldd --version | head -1 | tee "$RUN/glibc.txt"
nvidia-smi -L | tee "$RUN/gpu.txt"; nvidia-smi --query-gpu=driver_version --format=csv,noheader | tee -a "$RUN/gpu.txt"
git -C "$L/wt" rev-parse HEAD > "$RUN/HEAD"

echo "=== A: start_server.sh on the runtime as setup_12b.sh left it (prebuilt) $(date -u +%T)"
bash "$hpc/start_server.sh" > "$RUN/A-start_server.out" 2>&1; echo "A start_server exit $?" | tee "$RUN/A-exit.txt"
cat "$RUN/A-start_server.out"; for f in "$POD_LLM_STATE"/server-*.log; do [[ -f $f ]] && { echo "-- $f"; head -5 "$f"; cp "$f" "$RUN/A-$(basename "$f")"; }; done
bash "$hpc/stop_server.sh" || true

echo "=== A2: prebuilt with the 5 soname links restored, --version only $(date -u +%T)"
T=$L/gpu/symlink-test
LD_LIBRARY_PATH=$T "$T/llama-server" --version > "$RUN/A2-version.txt" 2>&1; echo "A2 exit $?" | tee -a "$RUN/A2-version.txt"; head -3 "$RUN/A2-version.txt"

echo "=== B: README fallback: build_llama_cuda.sh $(date -u +%T)"
module load arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0
module list 2>&1 | tee "$RUN/modules.txt"
mv "$POD_LLM_RUNTIME/llama-b11429-cuda" "$POD_LLM_RUNTIME/llama-b11429-cuda.prebuilt"
curl -sI -m 15 https://github.com > "$RUN/internet.txt" 2>&1; echo "github HEAD exit $? $(head -1 "$RUN/internet.txt")"
export BUILD_JOBS=8
t0=$(date +%s)
LDFLAGS="-L/apps/u/opt/gcc/14.2.0/cuda-toolkit/12.8.0/lib64/stubs" bash "$hpc/build_llama_cuda.sh" > "$RUN/B-build.log" 2>&1; b=$?
if [[ $b != 0 && ! -d $POD_LLM_RUNTIME/llama.cpp-src/.git ]]; then
  echo "clone failed on node; using staged clone"; rm -rf "$POD_LLM_RUNTIME/llama.cpp-src"; cp -r "$L/stage/llama.cpp-src" "$POD_LLM_RUNTIME/llama.cpp-src"; echo staged > "$RUN/B-src-origin.txt"
  LDFLAGS="-L/apps/u/opt/gcc/14.2.0/cuda-toolkit/12.8.0/lib64/stubs" bash "$hpc/build_llama_cuda.sh" >> "$RUN/B-build.log" 2>&1; b=$?
else echo node-clone > "$RUN/B-src-origin.txt"; fi
echo "B build exit $b, $(( $(date +%s) - t0 )) s" | tee "$RUN/B-exit.txt"; tail -3 "$RUN/B-build.log"
[[ $b == 0 ]] || exit 1
git -C "$POD_LLM_RUNTIME/llama.cpp-src" rev-parse HEAD > "$RUN/B-llama-src-commit.txt"

echo "=== C: setup_12b.sh again (files present, no download) $(date -u +%T)"
t0=$(date +%s); bash "$hpc/setup_12b.sh" > "$RUN/C-setup.out" 2>&1; echo "C setup exit $?, $(( $(date +%s) - t0 )) s" | tee "$RUN/C-exit.txt"
cat "$RUN/C-setup.out"; cp "$POD_LLM_RUNTIME/sha256.txt" "$RUN/C-sha256.txt"; cp "$POD_LLM_RUNTIME/runtime_manifest_12b.json" "$RUN/C-manifest.json"; cat "$RUN/C-manifest.json"

echo "=== D: start_server.sh with the built server, one request $(date -u +%T)"
t0=$(date +%s); bash "$hpc/start_server.sh" > "$RUN/D-start_server.out" 2>&1; s=$?; echo "D start_server exit $s, $(( $(date +%s) - t0 )) s" | tee "$RUN/D-exit.txt"; cat "$RUN/D-start_server.out"
if [[ $s == 0 ]]; then
  curl -s "http://127.0.0.1:$POD_LLM_PORT/v1/models" > "$RUN/D-models.json"
  t0=$(date +%s%N)
  curl -s -m 120 "http://127.0.0.1:$POD_LLM_PORT/v1/chat/completions" -H 'Content-Type: application/json' \
    -d '{"model":"gemma-4-12b-it-qat-q4_0-vision","max_tokens":64,"messages":[{"role":"user","content":"In one sentence, what does a POD (proper orthogonal decomposition) of a velocity field give you?"}]}' \
    > "$RUN/D-request.json"; echo "request exit $?, $(( ($(date +%s%N) - t0)/1000000 )) ms" | tee "$RUN/D-request-time.txt"
  cat "$RUN/D-request.json"; echo
  nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader | tee "$RUN/D-gpu-after.txt"
fi
for f in "$POD_LLM_STATE"/server-*.log; do [[ -f $f ]] && { tail -5 "$f"; }; done
bash "$hpc/stop_server.sh"; echo "stop exit $?"; date -u +%FT%TZ
