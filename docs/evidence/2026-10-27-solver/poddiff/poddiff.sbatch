#!/bin/bash
#SBATCH --job-name=pod-poddiff
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=01:30:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-poddiff-20261027/poddiff-%j.out
# Why did the sweep's POD mode files differ (<= 1e-11) from the baseline's while U, p, phi were
# identical? Candidates: two solver processes at once, BLAS threads. Runs the baseline case
# (600 steps) in four ways and compares every written file with run A.
set -euo pipefail
module load apptainer
OUT=/cluster/medbow/gscratch/syome/github_repos/pod-poddiff-20261027/run-$SLURM_JOB_ID
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
BIN=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/llm-demo-work/bin/PODFoam
mkdir -p "$OUT"
stage() {  # name
    local c="$OUT/$1"; mkdir -p "$c"
    for d in 0 constant system 0.1; do cp -r "$SRC/$d" "$c/"; done
    for f in "$SRC"/*.py; do cp "$f" "$c/"; done
    sed -i 's/^endTime .*/endTime 0.103;/' "$c/system/controlDict"
}
run() {  # name threads
    local c="$OUT/$1"
    apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
        source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
        export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:\$LD_LIBRARY_PATH PYTHON=/gscratch/syome/conda/s4f/bin/python3
        export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=$c/mpl
        export LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=100 LLM_RUN_ID=poddiff/$1
        export OPENBLAS_NUM_THREADS=$2 OMP_NUM_THREADS=$2 MKL_NUM_THREADS=$2
        cd $c && $BIN -case $c > log.PODFoam 2>&1; echo \"$1 exit \$?\""
}
for n in A-alone-1thread B-alone-free C-pair1-free D-pair2-free E-pair1-1thread F-pair2-1thread; do stage $n; done
run A-alone-1thread 1
run B-alone-free 8
run C-pair1-free 8 & run D-pair2-free 8 & wait
run E-pair1-1thread 1 & run F-pair2-1thread 1 & wait
/gscratch/syome/conda/s4f/bin/python3 - "$OUT" <<'PY'
import hashlib, json, re, sys
from pathlib import Path
out = Path(sys.argv[1])
ref = out / 'A-alone-1thread'
def times(c): return sorted((d for d in c.iterdir() if re.fullmatch(r'0\.1[0-9]*', d.name) and d.name != '0.1'), key=lambda d: float(d.name))
report = {}
for c in sorted(out.iterdir()):
    if not c.is_dir() or c == ref: continue
    same = differ = 0; names = set()
    for d in times(c):
        for f in sorted(p for p in d.rglob('*') if p.is_file()):
            o = ref / d.name / f.relative_to(d)
            if o.is_file() and hashlib.sha256(f.read_bytes()).hexdigest() == hashlib.sha256(o.read_bytes()).hexdigest(): same += 1
            else: differ += 1; names.add(f.name)
    report[c.name] = {'identical': same, 'differ': differ, 'differing_names': sorted(names)}
print(json.dumps(report, indent=1)); (out / 'comparison.json').write_text(json.dumps(report, indent=1) + '\n')
PY
grep -h "^ExecutionTime" $OUT/*/log.PODFoam | tail -0; for c in $OUT/*/; do echo "$(basename $c): $(grep -c '^Time = ' $c/log.PODFoam) steps, $(tail -1 $c/log.PODFoam)"; done
