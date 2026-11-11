#!/bin/bash
#SBATCH --job-name=podsmall
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/small
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/small/logs/%x-%j.out
# Environment: VER (8|v2012|v2106|v2212), CASEKIND (shipped|stab). Builds PODFoam at upstream 6fde869 and at
# branch pr/podfoam-snapshot-copy, runs the case with the recording module on both and with the Python-side
# copy module on upstream, and compares snapshot matrices and written fields.
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; S=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/siblings; N=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/small; SOLVER=PODFoam; STAGES="recording copy ported"
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=$W/images/of-v2212-dev.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown VER $VER"; exit 2;;
esac
OUT=$N/runs/$SOLVER-$VER-$CASEKIND-${SLURM_JOB_ID:-local}; mkdir -p "$OUT/src"
echo "OUT=$OUT host=$(hostname) start=$(date -Is)"
module load apptainer
git -C "$S/upstream" rev-parse HEAD > "$OUT/UPSTREAM"
git -C "$S/upstream" archive HEAD "Solver_Examples/$SOLVER" | tar -x -C "$OUT/src"
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$N/scripts/inner.sh" "$OUT" "$SOLVER" "$VER" "$RC" "$CASEKIND" "$STAGES"
echo "inner exit $?"
diff -u "$OUT/src/Solver_Examples/$SOLVER/PythonComm.H" "$OUT/src-ported/Solver_Examples/$SOLVER/PythonComm.H" > "$OUT/branch.diff"
/gscratch/syome/conda/s4f/bin/python3 "$S/round2/scripts/compare2.py" "$OUT" "$SOLVER" "$VER" | tee "$OUT/summary.txt"
echo "end=$(date -Is)"
