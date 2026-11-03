#!/bin/bash
#SBATCH --job-name=r2-slice3d-cpu
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=02:00:00
# Phase 1: build + validation at bf7a06e in of2212.sif, four 3D slice runs (300 steps, LLM_ENABLED=0),
# then the test set (solver frames + random windows) drawn with the worktree's renderer.
set -uo pipefail
S=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/slice-3d
job=${SLURM_JOB_ID:?}; RUN=$S/phase1-$job; mkdir -p "$RUN"
hostname | tee "$RUN/node.txt"; date -u +%FT%TZ > "$RUN/start.txt"
git -C "$S/wt" rev-parse HEAD > "$RUN/HEAD"; git -C "$S/wt" status --short > "$RUN/git-status.txt"
SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; sha256sum "$SIF" > "$RUN/image-sha256.txt"
module load apptainer
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$S/scripts/phase1_inner.sh" "$RUN" "$S/wt" v2212 /usr/lib/openfoam/openfoam2212/etc/bashrc
echo "inner exit $?"
/gscratch/syome/conda/s4f/bin/python3 -I "$S/scripts/make_windows.py" --wt "$S/wt" --run "$RUN" --design "$S/design.json" --output "$RUN/testset" 2>&1 | tee "$RUN/make_windows.out"
echo "make_windows exit ${PIPESTATUS[0]}"
date -u +%FT%TZ > "$RUN/end.txt"
