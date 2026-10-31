#!/bin/bash
# Inside the image: validation, then the documented run_demo.sh commands against the stand-in server.
# Environment from suites.sbatch: OUT REPO VER RC
source "$RC" > /dev/null 2>&1
export PYTHON=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH
export OPENFOAM_BASHRC=$RC POD_OPENFOAM_VERSION=$VER POD_WORKSPACE=$OUT
export POD_LLM_RUNTIME=$OUT/runtime POD_LLM_PORT=$((20000 + ${SLURM_JOB_ID:-0} % 10000)) POD_GIT_RECORDS=$OUT/git
mkdir -p "$POD_LLM_RUNTIME"
export LLM_MODEL=gemma-4-E2B-it-Q4_0-vision
/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/stub/llama-server --model stub --mmproj stub --alias "$LLM_MODEL" --port "$POD_LLM_PORT" --delay 2 > "$OUT/stub-server.log" 2>&1 &
pid=$!
echo "$pid" > "$POD_LLM_RUNTIME/server.pid"
trap 'kill "$pid" 2>/dev/null' EXIT
for _ in $(seq 1 50); do
    curl -s -m 2 "http://127.0.0.1:$POD_LLM_PORT/health" 2>/dev/null | grep -q ok && break
    "$PYTHON" -c "import urllib.request,sys; sys.exit(0 if b'ok' in urllib.request.urlopen('http://127.0.0.1:$POD_LLM_PORT/health', timeout=2).read() else 1)" 2>/dev/null && break
    sleep 0.2
done
echo "stub cmdline: $(tr '\0' ' ' < /proc/$pid/cmdline | cut -c1-120)"
cd "$REPO/Solver_Examples/PODFoam" || exit 1
step() { # step NAME COMMAND...
    local name=$1; shift
    "$@" > "$OUT/$name.log" 2>&1
    local status=$?
    echo "$name exit $status: $(tail -1 "$OUT/$name.log" | cut -c1-150)"
    return 0
}
step validation ./validation/run_v2106.sh
step sync ./llm_demo/run_demo.sh
POD_SUITE=async step async-v1 ./llm_demo/run_demo.sh
POD_SUITE=async LLM_IMAGE_STYLE=v2 LLM_KILL_JOIN_S=0.2 step async-v2 ./llm_demo/run_demo.sh
