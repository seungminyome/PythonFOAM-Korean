#!/bin/bash
#SBATCH --job-name=wrong-setup-after
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/after-run-%j.out
# After the GPU job: the combined report, one report per model and the reasons for the judge. JOB: the GPU job id.
set -euo pipefail
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup
SET=$HERE/wrong-setup-test-20261030
RUNS=$HERE/results/window-test-$JOB
export PATH=/gscratch/syome/conda/s4f/bin:$PATH OPENBLAS_NUM_THREADS=1
hostname; git -C "$REPO" rev-parse HEAD; git -C "$REPO" status --short
mkdir -p "$HERE/reports"
cd "$REPO/Solver_Examples/PODFoam/llm_demo"
sha256sum wrong_setup_test.py
python3 wrong_setup_test.py check --test-set "$SET"
python3 wrong_setup_test.py report "$RUNS/12b" "$RUNS/26b" "$RUNS/31b" "$RUNS/qwen35-35b" --test-set "$SET" \
    --output "$HERE/reports/combined.md" --reasons "$HERE/reports/reasons-to-judge.jsonl" > /dev/null
for key in 12b 26b 31b qwen35-35b; do
    python3 wrong_setup_test.py report "$RUNS/$key" --test-set "$SET" --output "$HERE/reports/$key.md" > /dev/null
done
cmp "$RUNS/report.md" "$HERE/reports/combined.md" && echo "the job's report.md equals reports/combined.md"
wc -l "$HERE"/reports/*
