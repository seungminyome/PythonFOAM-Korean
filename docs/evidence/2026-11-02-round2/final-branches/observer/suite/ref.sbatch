#!/bin/bash
#SBATCH --job-name=r4o-ref-v2212
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=00:45:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/observer/logs/ref-v2212-%j.out
# validation/run.sh on v2212 from the detached worktree wt-obs (24e9df6), workspace suite/refruns; a PASS becomes
# suite/ref-v2212 (POD_REFERENCE_RUN of the GPU suite). Pattern: r3/assemble/jobs/build_validate.sbatch.
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; R=$W/r4/observer
module load apptainer
export PYTHON=/gscratch/syome/conda/s4f/bin/python3 OPENFOAM_BASHRC=/usr/lib/openfoam/openfoam2212/etc/bashrc POD_OPENFOAM_VERSION=v2212
export POD_WORKSPACE=$R/suite/refruns; mkdir -p $POD_WORKSPACE
echo "job $SLURM_JOB_ID node $(hostname) HEAD $(git -C $R/wt-obs rev-parse HEAD)"
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c '
    set --; set +e; source "$OPENFOAM_BASHRC" > /dev/null 2>&1; set -e
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
    cd "'"$R"'/wt-obs/Solver_Examples/PODFoam" && ./validation/run.sh'
status=$?
run=$(ls -td $POD_WORKSPACE/pod-v2212.* 2>/dev/null | head -1)
echo "VALIDATION v2212 exit $status run $run"
grep -o '"status": "[A-Z]*"' "$run/verification.json" 2>/dev/null
if [[ $status == 0 ]]; then ln -sfn "$run" $R/suite/ref-v2212; echo "reference link $R/suite/ref-v2212 -> $run"; fi
echo "worktree status lines: $(git -C $R/wt-obs status --short | wc -l)"
exit $status
