#!/bin/bash
#SBATCH --job-name=wrong-setup-evidence
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --cpus-per-task=2
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030/jobs/evidence-copy-%j.out
# The records into docs/evidence/2026-10-30-wrong-setup/ and the recount there.
set -euo pipefail
EV=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-setup/docs/evidence/2026-10-30-wrong-setup
HERE=/cluster/medbow/gscratch/syome/github_repos/wrong-setup-20261030
sacct -j 24946869,24946879,24946942,24947055,24947079,24947089,24947316,24947320,24947327 --format=JobID%14,JobName%22,Account,Partition%18,NodeList%12,Start,End,State,ExitCode > "$HERE/jobs/sacct.txt"
FINAL_TESTS=24947320 /gscratch/syome/conda/s4f/bin/python3 jobs/make_evidence.py copy 24947089
cd "$EV"
/gscratch/syome/conda/s4f/bin/python3 -I recount.py
du -sh "$EV"
