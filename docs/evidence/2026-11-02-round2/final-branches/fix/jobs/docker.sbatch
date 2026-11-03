#!/bin/bash
#SBATCH --job-name=r4f-docker
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/logs/docker-%j.out
# validation/run.sh and run.sh --baseline at the r4/pr-fix tip (c7) and the r4/pr-observer tip (obs) inside the
# maintainer's Docker image (romitmaulik1/pythonfoam_docker as upstream-docker.sif: Ubuntu 18.04, OpenFOAM 8, Python 3.6.9),
# with the inner script of phase 3 (r3/solver/jobs/docker_inner.sh, unchanged).
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; A=$W/r4/fix
OUT=$A/docker-$SLURM_JOB_ID; mkdir -p $OUT
module load apptainer
echo "job $SLURM_JOB_ID node $(hostname)"
for n in ${DOCKER_TREES:-c7 obs}; do
  mkdir -p $OUT/$n/PF; cp -a $A/src/$n/. $OUT/$n/PF/
  echo "=== $n $(cut -c1-7 $A/src/$n/HEAD)"
  apptainer exec --bind /cluster/medbow/gscratch $W/pr/maint-review/images/upstream-docker.sif bash $W/r3/solver/jobs/docker_inner.sh $OUT/$n
  echo "inner exit $?"
done
echo done
