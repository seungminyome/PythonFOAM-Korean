#!/bin/bash
#SBATCH --job-name=pod-upstream-regression
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/slurm/upstream-regression-%x-%j.out
# An existing user's view: upstream's own Run_Case with upstream's python_module.py, solved by upstream's
# PODFoam and by this fork's PODFoam, in one OpenFOAM version. Environment: VER (8, v2106), REPO, OUT_ROOT.
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
REPO=${REPO:-/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-compat}
OUT_ROOT=${OUT_ROOT:-$W/regression-runs}
export KIND=${KIND:-shipped}
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown VER $VER"; exit 2;;
esac
OUT=$OUT_ROOT/$KIND-$VER-${SLURM_JOB_ID:-local}; mkdir -p "$OUT"
module load apptainer
git -C "$REPO" rev-parse HEAD > "$OUT/HEAD"; git -C "$REPO" rev-parse upstream/main > "$OUT/UPSTREAM"
mkdir -p "$OUT/src-upstream" "$OUT/src-fork"
git -C "$REPO" archive upstream/main Solver_Examples/PODFoam | tar -x -C "$OUT/src-upstream"
git -C "$REPO" archive HEAD Solver_Examples/PODFoam | tar -x -C "$OUT/src-fork"
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$W/matrix/upstream_regression_inner.sh" "$OUT" "$VER" "$RC"
echo "inner exit $?"
/gscratch/syome/conda/s4f/bin/python3 "$W/matrix/compare_regression.py" "$OUT"
