#!/bin/bash
#SBATCH --job-name=pod-ref-3
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
# The reference-run lines of hpc/README.md (as docs/evidence/2026-10-30-versions/scripts/gpu/reference.sh), once per image,
# from the unedited bf7a06e worktree. POD_WORKSPACE puts each pod-<ver>.XXXXXX under r2/gpu-suites/ref/.
# Then: a start directory per version = the 0.1 fields of job 24757460 beside that version's reference mesh
# (the bodies of points/faces/owner/neighbour equal; only the header, and inGroups spelling on 8, differ).
set -uo pipefail
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030; R=$W/r2/gpu-suites
SRC=$G/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
module load apptainer
export POD_LLM_RUNTIME=$G/PythonFOAM/llm-runtime-12b PYTHON=/gscratch/syome/conda/s4f/bin/python3 POD_WORKSPACE=$R/ref
hostname > $R/ref/node.txt
cd $R/wt-bf7a06e || exit 1
git rev-parse HEAD > $R/ref/HEAD; git status --short > $R/ref/git-status.txt
for VER in v2012 8 v2212; do
  case $VER in
    v2012) image=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
    v2212) image=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
    8)     image=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  esac
  export OPENFOAM_BASHRC=$RC POD_OPENFOAM_VERSION=$VER
  sha256sum "$image" > $R/ref/image-sha256-$VER.txt
  echo "=== $VER $(date -u +%T)"
  apptainer exec --bind /cluster/medbow/gscratch $image bash -c 'source "$OPENFOAM_BASHRC"
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
    cd Solver_Examples/PODFoam && ./validation/run_v2106.sh' > $R/ref/validation-$VER.log 2>&1
  echo "reference $VER exit $? $(date -u +%T)"; tail -1 $R/ref/validation-$VER.log | cut -c1-160
  ref=$(ls -dt $R/ref/pod-$VER.* | head -1)
  s=$R/start/$VER; mkdir -p $s/constant
  cp -r $ref/fixed-pod/constant/polyMesh $s/constant/
  cp -r $SRC/0.1 $s/
  for f in boundary faces neighbour owner points; do
    a=$(awk 'f{print} /^}/&&!f{f=1}' $SRC/constant/polyMesh/$f | sha256sum | cut -d' ' -f1)
    b=$(awk 'f{print} /^}/&&!f{f=1}' $s/constant/polyMesh/$f | sha256sum | cut -d' ' -f1)
    echo "$VER $f body_equal=$([[ $a == $b ]] && echo true || echo false) start=$(sha256sum $SRC/constant/polyMesh/$f | cut -c1-16) ref=$(sha256sum $s/constant/polyMesh/$f | cut -c1-16)"
  done | tee $R/start/mesh-check-$VER.txt
  diff $SRC/constant/polyMesh/boundary $s/constant/polyMesh/boundary > $R/start/boundary-diff-$VER.txt
done
echo "all done $(date -u +%T)"
