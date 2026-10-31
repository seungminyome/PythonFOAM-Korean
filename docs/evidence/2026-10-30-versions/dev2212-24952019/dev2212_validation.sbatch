#!/bin/bash
#SBATCH --job-name=pod-dev2212-final
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:30:00
# The bridge validation of this code in the image named in hpc/README.md (apptainer pull docker://opencfd/openfoam-dev:2212).
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; D=$W/pr/refix/dev2212-final
SIF=$W/images/of-v2212-dev.sif
module load apptainer
export PYTHON=/gscratch/syome/conda/s4f/bin/python3 OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc POD_OPENFOAM_VERSION=v2212
export POD_WORKSPACE=$D/run; mkdir -p "$POD_WORKSPACE"
echo "node $(hostname) job $SLURM_JOB_ID code $(cat $D/HEAD) image $SIF"
sha256sum "$SIF"
apptainer exec "$SIF" bash -c '
  set +e; source "$OPENFOAM_BASHRC" > /dev/null 2>&1; set -e
  export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
  echo "WM_PROJECT_VERSION $WM_PROJECT_VERSION"
  cd "'"$D"'/PythonFOAM/Solver_Examples/PODFoam" && ./validation/run_v2106.sh'
status=$?
echo "exit $status"
exit $status
