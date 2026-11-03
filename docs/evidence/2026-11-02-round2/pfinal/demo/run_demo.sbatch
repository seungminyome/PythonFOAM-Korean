#!/bin/bash
#SBATCH --job-name=pfinal-demo
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:40:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/pfinal/demo
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/pfinal/demo/slurm/pfinal-demo-%j.out
# Runtime demonstration of which pressure-solver dictionary (p or pFinal) each pressure corrector uses,
# on the stabilised PODFoam case, 2 time steps, for pimpleFoam of the image, the fork's PODFoam
# (pEqn.solve(mesh.solver(p.select(pimple.finalInnerIter()))) on openfoam.com), upstream's PODFoam
# (plain pEqn.solve()) and the fork built with upstream's line (fork-plainp), on v2012, v2106, v2212, 8.
# Binaries and cases come from the account runs listed in SRCRUN (jobs 24951137-24951140, fork bf7a06e, upstream 6fde869).
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
R=$W/r2/pfinal/demo
module load apptainer
for VER in v2012 v2106 v2212 8; do
  case $VER in
    v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc; SRCRUN=$W/account-runs/stabilised-v2012-24951138;;
    v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc; SRCRUN=$W/account-runs/stabilised-v2106-24951139;;
    v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc; SRCRUN=$W/account-runs/stabilised-v2212-24951140;;
    8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc; SRCRUN=$W/account-runs/stabilised-8-24951137;;
  esac
  OUT=$R/runs-${SLURM_JOB_ID}/$VER; mkdir -p "$OUT"
  echo "=== $VER  image $SIF  binaries/case from $SRCRUN"
  echo "$SRCRUN" > "$OUT/SRCRUN"; echo "$SIF" > "$OUT/SIF"
  apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash "$R/inner.sh" "$VER" "$OUT" "$SRCRUN" "$RC"
done
/gscratch/syome/conda/s4f/bin/python3 "$R/summarize.py" "$R/runs-${SLURM_JOB_ID}"
