#!/bin/bash
#SBATCH --job-name=ws2-build
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
# After the 60 runs: flow-check, build the six request sets, check them (leak check included),
# baselines on the primary frames, contact sheet. Fails loudly if any step fails.
set -euo pipefail
G=/cluster/medbow/gscratch/syome/github_repos
X=$G/wrong-setup-2-20261103
D=$X/repo/Solver_Examples/PODFoam/llm_demo
P=/gscratch/syome/conda/s4f/bin/python3
C=$(ls $G/wrong-setup-20261030/wrong-setup-test-20261030/frames/N1/*/fields.npz | head -1)
cd "$D"
$P wrong_setup_test2.py flow-check --design $G/flow-states-20261103/design.json --output $X/final/flow-check.json > $X/final/flow-check.out
grep -c refused $X/final/flow-check.json && { echo "flow-check refused runs"; exit 1; } || true
rm -rf $X/final/set
$P wrong_setup_test2.py build --design $G/flow-states-20261103/design.json --centres "$C" --output $X/final/set
$P wrong_setup_test2.py check --test-set $X/final/set
$P wrong_setup_test2.py baselines --test-set $X/final/set --output $X/final/baselines.json
$P wrong_setup_test2.py contact --test-set $X/final/set --output $X/final/contact-8000.png --step 8000
echo BUILD_DONE
