#!/bin/bash
#SBATCH --job-name=pod-callback-check
#SBATCH --account=me5475
#SBATCH --partition=mb
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:30:00
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-callback-20261028/callback-check-%j.out
# The callback of branch callback-telemetry-trends against main's (2ed6da2, callback-main/), on the
# staged step case (2D backward-facing step, 20,540 cells, developed flow from t = 0.1 s), 1,250
# steps of 5e-6 s, LLM_ENABLED=0 (frames drawn, nothing sent), v2 pictures of x 0..0.12 m, y 0..0.04 m:
#   describe-main, describe-new            a describe request at step 100
#   sequence-main, sequence-new            a sequence with frames at steps 100, 150 and 200
#   sequence-tn-new                        the same with LLM_SEQUENCE_PROMPT=tn (the branch only)
#   par2-describe-main, par2-describe-new  the describe case on 2 MPI ranks
# Then compare.py (every file, telemetry.jsonl, the records), memory.py (24,000 recorded states,
# tracemalloc), the unit tests, and verify_async.py of the branch on the October 22 suite.
set -euo pipefail
module load apptainer
OUT=/cluster/medbow/gscratch/syome/github_repos/pod-callback-20261028/run-$SLURM_JOB_ID
REPO=/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-cb
DEMO=$REPO/Solver_Examples/PODFoam/llm_demo
EVID=$REPO/docs/evidence/2026-10-28-callback
SRC=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ/async-no-llm
SUITE=/cluster/medbow/gscratch/syome/github_repos/pod-async-v2/run-24757460/pod-llm-async.UM1RyJ
PY=/gscratch/syome/conda/s4f/bin/python3
mkdir -p "$OUT"
git -C "$REPO" rev-parse HEAD > "$OUT/HEAD"; git -C "$REPO" status --short > "$OUT/git-status.txt"; git -C "$REPO" diff > "$OUT/changes.patch"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
apptainer exec --bind /cluster/medbow/gscratch /cluster/medbow/gscratch/syome/s4f/of2212.sif bash -c "
source /usr/lib/openfoam/openfoam2212/etc/bashrc >/dev/null 2>&1 || true
set -eo pipefail   # not -u: the OpenFOAM bashrc reads unset variables
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:\$LD_LIBRARY_PATH PYTHON=$PY POD_OPENFOAM_VERSION=v2212
export POD_WORKSPACE=$OUT
cd $REPO/Solver_Examples/PODFoam && ./validation/run_v2106.sh > $OUT/validation.log 2>&1 && echo 'validation ran' || echo 'validation FAILED'
grep -E 'PASS|FAIL' $OUT/validation.log | tail -2
exe=\$(ls -d $OUT/pod-v2212.*/bin/PODFoam | head -1); echo \"exe=\$exe\"
export PYTHONHOME=/gscratch/syome/conda/s4f
export LLM_ENABLED=0 LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
for name in describe-main describe-new sequence-main sequence-new sequence-tn-new par2-describe-main par2-describe-new; do
    c=$OUT/\$name; mkdir -p \$c
    for d in 0 constant system 0.1; do cp -r $SRC/\$d \$c/; done
    cp $SRC/pod_svd.py \$c/
    for f in bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py python_module.py; do cp $DEMO/\$f \$c/; done
    if [[ \$name == *-main ]]; then cp $EVID/callback-main/python_module.py \$c/python_module.py; fi
    sed -i 's/^endTime .*/endTime 0.10625;/' \$c/system/controlDict
    config=\${name%-main}; config=\${config%-new}
    unset LLM_MODE LLM_ANALYSIS_STEP LLM_SEQUENCE_STEPS LLM_SEQUENCE_PROMPT
    case \$config in
        *describe) export LLM_MODE=describe LLM_ANALYSIS_STEP=100 ;;
        sequence) export LLM_MODE=sequence LLM_SEQUENCE_STEPS=100,150,200 ;;
        sequence-tn) export LLM_MODE=sequence LLM_SEQUENCE_STEPS=100,150,200 LLM_SEQUENCE_PROMPT=tn ;;
    esac
    export MPLCONFIGDIR=\$c/mpl LLM_RUN_ID=callback-check/\$config
    if [[ \$name == par2-* ]]; then
        # the case's POD module refuses ranks other than 0; as in the 2026-10-27 MPI test
        sed -i 's/if rank != 0:/if False:/; s/if rank != 0 or not _snapshots:/if not _snapshots:/' \$c/pod_svd.py
        (cd \$c && sed -i 's/^numberOfSubdomains .*/numberOfSubdomains 2;/; s/^method .*/method scotch;/' system/decomposeParDict && decomposePar > log.decomposePar 2>&1 && mpirun --oversubscribe -np 2 \$exe -parallel -case \$c > log.PODFoam 2>&1; echo \"\$name exit \$?\")
    else
        (cd \$c && \$exe -case \$c > log.PODFoam 2>&1; echo \"\$name exit \$?\")
    fi
    grep -E 'PYTHON LLM (step|telemetry)|Python finalized|^End' \$c/log.PODFoam | head -4
done
"
set +e
$PY $EVID/compare.py "$OUT" > "$OUT/compare.log" 2>&1; echo "compare exit $?"; tail -2 "$OUT/compare.log"
$PY $EVID/memory.py --output "$OUT/memory.json" > "$OUT/memory.log" 2>&1; echo "memory exit $?"; cat "$OUT/memory.log"
(cd $DEMO && $PY -m unittest test_llm_client test_callback test_ablation_runner test_async test_picture_test > "$OUT/unit-tests.log" 2>&1; echo "unit tests exit $?")
grep -E '^Ran |^OK|^FAILED' "$OUT/unit-tests.log"
$PY $DEMO/verify_async.py $SUITE > "$OUT/verify-oct22-suite.json" 2> "$OUT/verify-oct22-suite.err"; echo "verify_async on the October 22 suite exit $?"
grep -m1 '"status"' "$OUT/verify-oct22-suite.json" || tail -3 "$OUT/verify-oct22-suite.err"
