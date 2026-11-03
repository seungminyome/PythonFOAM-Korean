#!/bin/bash
#SBATCH --job-name=r4t-docker-e2e
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/texts
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/texts/logs/docker-e2e-%j.out
# Runs docker_e2e.sh (the PR bodies' Docker how-to) in the Apptainer copy of
# romitmaulik1/pythonfoam_docker, once per branch, each in a fresh /tmp.
# Usage: sbatch docker_e2e.sbatch CLONE_URL [BRANCH[=EXPECTED_COMMIT] ...]
#   default branches: pr/podfoam-fix pr/podfoam-observer
#   e.g. sbatch docker_e2e.sbatch https://github.com/seungminyome/PythonFOAM.git \
#          pr/podfoam-fix=8954b2544d0f pr/podfoam-observer=24e9df6f5640
# --containall: no host home, environment or /tmp (as in Docker); a job folder is bound
# at /tmp because Apptainer's own /tmp is a 64 MB tmpfs. A local repository path given as
# file:///... is bound read-only so that the wrapper can be tested before the push.
set -u
T=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/texts
IMG=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/maint-review/images/upstream-docker.sif
url=${1:?usage: sbatch docker_e2e.sbatch CLONE_URL [BRANCH[=EXPECTED_COMMIT] ...]}
shift
[[ $# == 0 ]] && set -- pr/podfoam-fix pr/podfoam-observer
# module is a shell function only in login shells; load Lmod if needed, else use the known path.
if ! command -v apptainer > /dev/null; then
    type module > /dev/null 2>&1 || source /apps/s/lmod/latest/init/bash > /dev/null 2>&1
    module load apptainer > /dev/null 2>&1 || export PATH=/apps/s/apptainer/1.4.1/bin:$PATH
fi
command -v apptainer || { echo "apptainer not found"; exit 3; }
OUT=$T/e2e-${SLURM_JOB_ID:-local}
mkdir -p "$OUT"
binds=(--bind "$T/docker_e2e.sh:/e2e/docker_e2e.sh:ro")
if [[ $url == file://* ]]; then
    binds+=(--bind "${url#file://}:${url#file://}:ro")
fi
echo "job ${SLURM_JOB_ID:-local} node $(hostname) url $url image $(sha256sum "$IMG" | cut -c1-12)"
fails=0
for spec in "$@"; do
    branch=${spec%%=*}
    expect=""; [[ $spec == *=* ]] && expect=${spec#*=}
    tag=${branch//\//_}
    mkdir -p "$OUT/$tag/tmp" "$OUT/$tag/home"
    echo "=== $branch (expected commit: ${expect:-not given})"
    apptainer exec --containall --home "$OUT/$tag/home" --bind "$OUT/$tag/tmp:/tmp" "${binds[@]}" \
        "$IMG" bash /e2e/docker_e2e.sh "$url" "$branch" > "$OUT/$tag/e2e.log" 2>&1
    rc=$?
    grep -E '^(remote head|Validation directory|verification|E2E )' "$OUT/$tag/e2e.log"
    tail -3 "$OUT/$tag/e2e.log" | tr '\r' '\n' | tail -3 | sed 's/^/  log: /'
    last=$(grep "^E2E " "$OUT/$tag/e2e.log" | tail -1)
    got=$(awk '{print $3}' <<< "$last")
    result=FAIL
    [[ $rc == 0 && $last == "E2E $branch "*" PASS 0" ]] && result=PASS
    if [[ -n $expect && $got != "$expect"* ]]; then
        result=FAIL; echo "commit $got does not start with $expect"
    fi
    echo "RESULT $branch $got $result (exit $rc)"
    [[ $result == PASS ]] || fails=$((fails + 1))
done
echo "done: $fails failed"
exit $fails
