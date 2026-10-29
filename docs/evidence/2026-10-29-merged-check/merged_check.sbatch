#!/bin/bash
#SBATCH --job-name=pod-merged-check
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=01:30:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-merged-20261029/merged-check-%j.out
# The merged main (callback, instability test, 3D slice, record_written) in a real solver run:
# build + bridge validation; the 2D step case with the v2 frame at step 100 (compared byte for
# byte with the serial frame and request body of the 2026-10-27 MPI test, job 24903786); the 3D
# case of the slice test with the frame at step 100 (compared with run-24929629's serial3d frame).
set -uo pipefail
module load apptainer
OUT=/cluster/medbow/gscratch/syome/github_repos/pod-merged-20261029/run-$SLURM_JOB_ID
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
CASE3D=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/case3d
mkdir -p "$OUT"
git -C "$REPO" rev-parse HEAD > "$OUT/HEAD"; git -C "$REPO" status --short > "$OUT/git-status.txt"
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
set -eo pipefail
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:\$LD_LIBRARY_PATH PYTHON=\$PY POD_OPENFOAM_VERSION=v2212 POD_WORKSPACE=$OUT
(cd $REPO/Solver_Examples/PODFoam && ./validation/run_v2106.sh > $OUT/validation.log 2>&1) && echo 'validation ran' || echo 'validation FAILED'
grep -E 'PASS|FAIL' $OUT/validation.log | tail -1
exe=\$(ls -d $OUT/pod-v2212.*/bin/PODFoam | head -1)
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=100 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
for name in serial2d serial3d; do
    c=$OUT/\$name; mkdir -p \$c
    if [[ \$name == serial2d ]]; then for d in 0 constant system 0.1; do cp -r $SRC/\$d \$c/; done
    else cp -r $CASE3D/constant $CASE3D/system $CASE3D/0.1 \$c/; fi
    cp $SRC/pod_svd.py \$c/
    for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do cp $REPO/Solver_Examples/PODFoam/llm_demo/\$f \$c/; done
    sed -i 's/^endTime .*/endTime 0.10055;/; s/^writeInterval .*/writeInterval 250;/' \$c/system/controlDict
    (cd \$c && env MPLCONFIGDIR=\$c/mpl LLM_RUN_ID=\$( [[ \$name == serial2d ]] && echo mpi-test/serial || echo slice-test/serial3d ) \$exe -case \$c > log.PODFoam 2>&1; echo \"\$name exit \$?\")
    grep -E 'POD observer plane slice|PYTHON LLM mesh|PYTHON LLM step|PYTHON LLM telemetry|Python finalized|^End' \$c/log.PODFoam | head -6
done
"
/gscratch/syome/conda/s4f/bin/python3 - "$OUT" <<'PY'
import hashlib, json, sys
from pathlib import Path
out = Path(sys.argv[1])
refs = {'serial2d': Path('/cluster/medbow/gscratch/syome/github_repos/pod-mpi-20261027/run-24903786/serial'),
        'serial3d': Path('/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/serial3d')}
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
report = {'HEAD': (out / 'HEAD').read_text().strip()}
for name, ref in refs.items():
    case = out / name
    frame, rframe = case / 'llm_observation/step-000100', ref / 'llm_observation/step-000100'
    files = sorted(p.name for p in rframe.iterdir())
    tel = case / 'telemetry.jsonl'
    report[name] = {
        'frame_files_identical': {f: (frame / f).exists() and sha(frame / f) == sha(rframe / f) for f in files},
        'request_body_identical': sha(case / 'llm_request_body.json') == sha(ref / 'llm_request_body.json'),
        'telemetry_lines': len(tel.read_text().splitlines()) if tel.exists() else None,
        'telemetry_tmp_left': (case / 'telemetry.jsonl.tmp').exists(),
        'ended': '\nEnd\n' in (case / 'log.PODFoam').read_text(),
        'result_status': json.loads((case / 'llm_result.json').read_text()).get('status'),
    }
report['pass'] = all(all(v['frame_files_identical'].values()) and v['request_body_identical'] and v['telemetry_lines'] == 110
                     and not v['telemetry_tmp_left'] and v['ended'] for k, v in report.items() if k.startswith('serial'))
print(json.dumps(report, indent=1)); (out / 'merged-check.json').write_text(json.dumps(report, indent=1) + '\n')
PY
