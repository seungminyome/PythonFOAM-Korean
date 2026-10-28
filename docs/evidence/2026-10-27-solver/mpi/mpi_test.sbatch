#!/bin/bash
#SBATCH --job-name=pod-mpi-test
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:30:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-mpi-20261027/mpi-test-%j.out
# Build the solver with the gathered observer, run the bridge validation (serial), then the
# same 600-step case serially and on 2 ranks with LLM_ENABLED=0 (v2 frames at step 100), and
# compare the frames: the parallel frame's cells, sorted by centre, must equal the serial one's.
set -euo pipefail
module load apptainer
OUT=/cluster/medbow/gscratch/syome/github_repos/pod-mpi-20261027/run-$SLURM_JOB_ID
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
mkdir -p "$OUT"
git -C "$REPO" rev-parse HEAD > "$OUT/HEAD"; git -C "$REPO" status --short > "$OUT/git-status.txt"; git -C "$REPO" diff > "$OUT/changes.patch"
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
set -eo pipefail   # not -u: the OpenFOAM bashrc reads unset variables
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:\$LD_LIBRARY_PATH PYTHON=/gscratch/syome/conda/s4f/bin/python3 POD_OPENFOAM_VERSION=v2212
export POD_WORKSPACE=$OUT
cd $REPO/Solver_Examples/PODFoam && ./validation/run_v2106.sh > $OUT/validation.log 2>&1 && echo 'validation ran' || echo 'validation FAILED'
grep -E 'PASS|FAIL' $OUT/validation.log | tail -2
exe=\$(ls -d $OUT/pod-v2212.*/bin/PODFoam | head -1); echo \"exe=\$exe\"
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=100 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
for name in serial par2; do
    c=$OUT/\$name; mkdir -p \$c
    for d in 0 constant system 0.1; do cp -r $SRC/\$d \$c/; done
    for f in $SRC/*.py; do cp \$f \$c/; done
    for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do cp $REPO/Solver_Examples/PODFoam/llm_demo/\$f \$c/; done
    sed -i 's/^endTime .*/endTime 0.103;/' \$c/system/controlDict
    # the validation POD module refuses other ranks; the test keeps per-rank snapshots instead
    sed -i 's/if rank != 0:/if False:/; s/if rank != 0 or not _snapshots:/if not _snapshots:/' \$c/pod_svd.py
    export MPLCONFIGDIR=\$c/mpl LLM_RUN_ID=mpi-test/\$name
    if [[ \$name == serial ]]; then
        (cd \$c && \$exe -case \$c > log.PODFoam 2>&1; echo \"serial exit \$?\")
    else
        (cd \$c && sed -i 's/^numberOfSubdomains .*/numberOfSubdomains 2;/; s/^method .*/method scotch;/' system/decomposeParDict && decomposePar > log.decomposePar 2>&1 && mpirun --oversubscribe -np 2 \$exe -parallel -case \$c > log.PODFoam 2>&1; echo \"par2 exit \$?\"; reconstructPar -latestTime > log.reconstructPar 2>&1 || true)
    fi
    grep -E 'POD mesh geometry|PYTHON LLM step|Python finalized|^End' \$c/log.PODFoam | head -4
done
"
/gscratch/syome/conda/s4f/bin/python3 - "$OUT" <<'PY'
import json, sys
from pathlib import Path
import numpy as np
out = Path(sys.argv[1])
def load(case):
    z = np.load(case / 'llm_observation' / 'step-000100' / 'fields.npz')
    return np.array(z['centres']), np.array(z['U']), np.array(z['p'])
cs, us, ps = load(out / 'serial'); cp, up, pp = load(out / 'par2')
print('cells serial', len(cs), 'par2', len(cp))
order_s = np.lexsort((cs[:, 1], cs[:, 0])); order_p = np.lexsort((cp[:, 1], cp[:, 0]))
dc = np.abs(cs[order_s] - cp[order_p]).max(); du = np.abs(us[order_s] - up[order_p]).max(); dp = np.abs(ps[order_s] - pp[order_p]).max()
report = {'cells': [int(len(cs)), int(len(cp))], 'max_abs_diff_centres_m': float(dc), 'max_abs_diff_U': float(du), 'max_abs_diff_p': float(dp),
          'max_abs_U': float(np.abs(us).max()), 'max_abs_p': float(np.abs(ps).max())}
print(json.dumps(report, indent=1)); (out / 'frame-comparison.json').write_text(json.dumps(report, indent=1) + '\n')
PY
