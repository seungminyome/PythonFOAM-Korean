#!/bin/bash
#SBATCH --job-name=pod-gpu-versions
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=01:00:00
# Part A: one llama-server on the host GPU (hpc/start_server.sh, the settings of hpc/async_v2.slurm); for each of the
# four OpenFOAM images, in the image: build + validation from the clone, then the 2D step case (110 steps from 0.1 s)
# with one real describe request at step 100.
set -uo pipefail
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030; A=$W/pr/refix/gpu-a
REPO=$A/PythonFOAM; hpc=$REPO/Solver_Examples/PODFoam/llm_demo/hpc
job=${SLURM_JOB_ID:?}; RUN=$A/run-$job; mkdir -p "$RUN"
export POD_LLM_RUNTIME=$G/PythonFOAM/llm-runtime-12b POD_LLM_STATE=$RUN/server POD_LLM_PORT=$((20000 + job % 10000))
export LLM_MODEL=gemma-4-12b-it-qat-q4_0-vision LLM_CTX=4096 LLM_BATCH=512 LLM_UBATCH=512
export POD_HOST_MODULES="arcc/1.0 gcc/14.2.0 cuda-toolkit/12.8.0"
stop() { bash "$hpc/stop_server.sh" || true; if [[ -n ${spid:-} ]]; then kill -0 "$spid" 2>/dev/null && echo "SERVER STILL ALIVE pid $spid" || echo "server stopped (pid $spid gone)"; fi; }
trap stop EXIT
trap 'echo "signal TERM"; exit 143' TERM
hostname | tee "$RUN/node.txt"
git -C "$REPO" rev-parse HEAD | tee "$RUN/HEAD"; git -C "$REPO" status --short > "$RUN/git-status.txt"
nvidia-smi -L | tee "$RUN/gpu.txt"
nvidia-smi > "$RUN/nvidia-smi.txt" 2>&1
( module load $POD_HOST_MODULES; bash "$hpc/start_server.sh" ); s=$?
echo "start_server exit $s"
[[ $s == 0 ]] || { tail -20 "$POD_LLM_STATE"/server-*.log; exit 1; }
spid=$(cat "$POD_LLM_STATE/server.pid")
module load apptainer
for VER in v2012 v2106 v2212 8; do
  case $VER in
    v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
    v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
    v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
    8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  esac
  OUT=$RUN/$VER; mkdir -p "$OUT"; sha256sum "$SIF" > "$OUT/image-sha256.txt"
  echo "=== $VER $(date -u +%T)"
  apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$A/part_a_inner.sh" "$OUT" "$REPO" "$VER" "$RC" "$POD_LLM_PORT"
  echo "$VER inner exit $? $(date -u +%T)"
  nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader | tee -a "$RUN/gpu-after.txt"
  kill -0 "$spid" 2>/dev/null || echo "server gone after $VER"
done
/gscratch/syome/conda/s4f/bin/python3 "$A/part_a_check.py" "$RUN" "$REPO" 2>&1 | tee "$RUN/check.out"
echo "check exit ${PIPESTATUS[0]}"
