#!/bin/bash
#SBATCH --job-name=wrong-setup-prepare2
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:15:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/prepare-again-%j.out
# The ten cases written again with the committed wrong_setup_test.py and compared with those that ran
# (system, constant, the start directory 0.1, design.json apart from the folder name).
set -uo pipefail
export PATH=/gscratch/syome/conda/s4f/bin:$PATH OPENBLAS_NUM_THREADS=1
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup
FLOW=/cluster/medbow/gscratch/syome/github_repos/flow-states-20261030
TMP=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/prepare-again-$SLURM_JOB_ID
hostname; git -C "$REPO" rev-parse HEAD; sha256sum "$REPO/Solver_Examples/PODFoam/llm_demo/wrong_setup_test.py"
cd "$REPO/Solver_Examples/PODFoam/llm_demo"
python3 wrong_setup_test.py prepare --long /cluster/medbow/gscratch/syome/github_repos/flow-states-20261022/long-100ms --output "$TMP" > /dev/null
bad=0
for r in N1 N2 N3 N4 N5 M1-inlet-speed M2-viscosity M3-slip-walls M4-moving-wall M5-half-inlet; do
    for d in system constant 0.1; do
        diff -rq "$FLOW/$r/$d" "$TMP/$r/$d" > /dev/null && echo "$r/$d identical" || { echo "$r/$d DIFFERS"; bad=1; }
    done
done
sed "s#$TMP#$FLOW#g" "$TMP/design.json" | cmp - "$FLOW/design.json" && echo "design.json identical apart from the folder name" || bad=1
rm -rf "$TMP"
echo "problems: $bad"
