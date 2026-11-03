#!/bin/bash
#SBATCH --job-name=sib2
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/siblings/round2
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/siblings/round2/logs/%x-%j.out
# Environment: SOLVER, VER (8|v2106), CASEKIND (shipped|stab), STAGES ("recording copy ported")
set -uo pipefail
G=/cluster/medbow/gscratch/syome/github_repos
W=$G/pod-versions-20261030
S=$W/r2/siblings
case $VER in
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown VER $VER"; exit 2;;
esac
OUT=$S/round2/runs/$SOLVER-$VER-$CASEKIND-${SLURM_JOB_ID:-local}; mkdir -p "$OUT"
echo "OUT=$OUT host=$(hostname) start=$(date -Is) stages=$STAGES"
module load apptainer
git -C "$S/upstream" rev-parse HEAD > "$OUT/UPSTREAM"
mkdir -p "$OUT/src"
git -C "$S/upstream" archive HEAD "Solver_Examples/$SOLVER" | tar -x -C "$OUT/src"
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$S/round2/scripts/inner2.sh" "$OUT" "$SOLVER" "$VER" "$RC" "$CASEKIND" "$STAGES"
echo "inner exit $?"
/gscratch/syome/conda/s4f/bin/python3 "$S/round2/scripts/compare2.py" "$OUT" "$SOLVER" "$VER" | tee "$OUT/summary.txt"
echo "end=$(date -Is)"
