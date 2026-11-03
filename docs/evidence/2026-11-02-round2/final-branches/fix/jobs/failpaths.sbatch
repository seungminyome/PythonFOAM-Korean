#!/bin/bash
#SBATCH --job-name=r4f-failpaths
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:40:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/failpaths
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/logs/failpaths-%j.out
# validation/run.sh of the r4/pr-fix tip (src/c7) on v2106 with one deliberate failure each in a copy of the tree:
# wmake (#error in PODFoam.C), blockMesh (broken blockMeshDict), pimpleFoam (broken 0/p), PODFoam (svd_func raises).
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; F=$W/r4/fix; OUT=$F/failpaths/$SLURM_JOB_ID; mkdir -p $OUT
SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc
echo "job $SLURM_JOB_ID node $(hostname) code $(cat $F/src/c7/HEAD)"
module load apptainer
for kind in wmake blockMesh pimpleFoam PODFoam; do
  T=$OUT/$kind; mkdir -p $T; cp -a $F/src/c7/Solver_Examples $T/
  P=$T/Solver_Examples/PODFoam
  case $kind in
    wmake) echo '#error deliberate failure' >> $P/PODFoam.C;;
    blockMesh) sed -i 's/^vertices/verticesBROKEN/' $P/Run_Case/system/blockMeshDict;;
    pimpleFoam) sed -i 's/^internalField/internalFieldBROKEN/' $P/Run_Case/0/p;;
    PODFoam) printf '\ndef svd_func(rank):\n    raise RuntimeError("deliberate failure")\n' >> $P/validation/python_module.py;;
  esac
  apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash -c '
    set --; set +e; source "'"$RC"'" > /dev/null 2>&1
    export PYTHON=/gscratch/syome/conda/s4f/bin/python3 POD_WORKSPACE="'"$T"'/ws" LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH
    cd "'"$P"'" && ./validation/run.sh' > $T/stdout.txt 2> $T/stderr.txt
  status=$?
  echo "FAILPATH $kind exit $status stderr: $(tail -n 1 $T/stderr.txt | cut -c1-220)"
  log=$(tail -n 1 $T/stderr.txt | sed -n 's/.*failed; see //p'); [[ -n $log && -f $log ]] && echo "   named log exists: $log ($(wc -l < $log) lines)"
done
echo done
