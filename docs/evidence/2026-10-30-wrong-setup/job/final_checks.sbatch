#!/bin/bash
#SBATCH --job-name=wrong-setup-final
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/final-checks-%j.out
# The job records, what a judge needs and the recount in the evidence folder, the manifest written, then every
# manifest and the relative links checked and the recount run again.
set -uo pipefail
PY=/gscratch/syome/conda/s4f/bin/python3
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
EV=docs/evidence/2026-10-30-wrong-setup
hostname; git rev-parse HEAD
sacct -j 24946869,24946879,24946942,24947055,24947079,24947089,24947316,24947320,24947327,24947868 --format=JobID%14,JobName%22,Account,Partition%18,NodeList%12,Start,End,State,ExitCode > "$HERE/jobs/sacct.txt"
(cd "$EV/flow" && $PY -I judge_facts.py > /dev/null) || echo "judge_facts FAILED"
(cd "$EV" && $PY -I recount.py) || echo "recount FAILED"
$PY "$HERE/jobs/make_evidence.py" refresh \
    "pimpleFoam runs: job 24946879 (array 0 to 9), cases written by job 24946869" "set: build 24946942" \
    "models: window-test-24947089" "report and reasons: 24947316" "unit tests: 24947320" "cases written again and compared: 24947327" \
    "frame facts: 24947868"
echo "== check_manifest"; $PY docs/evidence/check_manifest.py | tail -8; echo "exit ${PIPESTATUS[0]}"
echo "== check_links"; $PY docs/check_links.py | tail -5; echo "exit ${PIPESTATUS[0]}"
echo "== recount again"; before=$(sha256sum "$EV/recount.json"); (cd "$EV" && $PY -I recount.py); after=$(sha256sum "$EV/recount.json")
[ "$before" = "$after" ] && echo "recount.json unchanged" || echo "recount.json CHANGED"
git status --short | head -30
