#!/bin/bash
# The Docker how-to of the PR bodies, as a test. Runs inside romitmaulik1/pythonfoam_docker
# (Ubuntu 18.04, OpenFOAM 8 in /opt/openfoam8, python3 with numpy), as root in Docker or as
# the user under Apptainer (docker_e2e.sbatch binds a job folder at /tmp).
# Usage: docker_e2e.sh CLONE_URL [BRANCH]   (BRANCH default pr/podfoam-fix)
# Docker:  docker run --rm -v "$PWD":/e2e romitmaulik1/pythonfoam_docker \
#            bash /e2e/docker_e2e.sh https://github.com/seungminyome/PythonFOAM.git pr/podfoam-fix
# Last line: "E2E <branch> <commit> PASS|FAIL <run.sh exit>". Exit status 0 only when run.sh
# exits 0 and verification.json says PASS; 1 otherwise, also when verification.json is missing.
# No set -u / set -e: the commands run as typed in an interactive shell (OpenFOAM's bashrc
# is not nounset-safe).
url=${1:?usage: docker_e2e.sh CLONE_URL [BRANCH]}
branch=${2:-pr/podfoam-fix}
dest=/tmp/PythonFOAM
rm -rf "$dest"
echo "remote head: $(git ls-remote "$url" "refs/heads/$branch")"
# Why a clone: /home/PythonFOAM in the image is commit 539dab9, which has no validation/,
# and /home is read-only under Apptainer. The branch is cloned into /tmp, as the PR bodies say.
# --- the commands of the PR body, verbatim except for the URL and branch variables ---
git clone --depth 1 -b "$branch" "$url" /tmp/PythonFOAM || { echo "E2E $branch - FAIL clone"; exit 1; }
source /opt/openfoam8/etc/bashrc
cd /tmp/PythonFOAM/Solver_Examples/PODFoam
./validation/run.sh
rc=$?
# --- end of the PR body commands ---
commit=$(git -C "$dest" rev-parse HEAD)
status=$(grep -ho '"status": "[A-Z]*"' "$dest"/Solver_Examples/PODFoam/validation/runs/pod-8.*/verification.json 2>/dev/null | head -1)
echo "verification: ${status:-none}"
if [[ $rc == 0 && "$status" == '"status": "PASS"' ]]; then
    echo "E2E $branch $commit PASS $rc"
    exit 0
fi
echo "E2E $branch $commit FAIL $rc"
exit 1
