#!/bin/bash
#SBATCH --job-name=r4f-sib
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/logs/sib-%x-%j.out
# Builds PODFoam_Debug, APMOSFoam and AEFoam from the export of r4/pr-fix commit 2 (src/c2). Environment: VER.
# On 8 (RECORD=1) also runs PODFoam_Debug on the shipped case with the snapshot-recording module, using
# r2/siblings round2 inner2.sh (stage "recording", built from this export) and compare2.py.
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; F=$W/r4/fix; S2=$W/r2/siblings
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown VER $VER"; exit 2;;
esac
OUT=$F/siblings/$VER-$SLURM_JOB_ID; mkdir -p $OUT/src
cp $F/src/c2/HEAD $OUT/HEAD; echo "job $SLURM_JOB_ID node $(hostname) code $(cat $OUT/HEAD)"
cp -r $F/src/c2/Solver_Examples $OUT/src/
module load apptainer
export OUT RC
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash -c '
  set --; source "$RC" > /dev/null 2>&1 || true
  PY=/gscratch/syome/conda/s4f/bin/python3
  export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH
  export PYTHON_INCLUDE_PATH=$($PY -c "import sysconfig; print(sysconfig.get_path(\"include\"))")
  export NUMPY_INCLUDE_PATH=$($PY -c "import numpy; print(numpy.get_include())")
  export PYTHON_LIB_PATH=$($PY -c "import sysconfig; print(sysconfig.get_config_var(\"LIBDIR\"))")
  export PYTHON_LIB_NAME=lpython$($PY -c "import sysconfig; print(sysconfig.get_config_var(\"LDVERSION\"))")
  echo "WM_PROJECT_VERSION=$WM_PROJECT_VERSION"
  for SOLVER in PODFoam_Debug APMOSFoam AEFoam; do
    export FOAM_USER_APPBIN=$OUT/bin-$SOLVER FOAM_MODULE_APPBIN=$OUT/bin-$SOLVER; mkdir -p "$FOAM_USER_APPBIN"
    if (cd "$OUT/src/Solver_Examples/$SOLVER" && wmake > "$OUT/log.build-$SOLVER" 2>&1) && [[ -x $OUT/bin-$SOLVER/$SOLVER ]]; then
      echo "BUILD $SOLVER ok $(stat -c %s $OUT/bin-$SOLVER/$SOLVER) bytes warnings $(grep -c -i warning $OUT/log.build-$SOLVER)"
    else
      echo "BUILD $SOLVER FAILED"; grep -n -iE "error" "$OUT/log.build-$SOLVER" | head -20 | cut -c1-240
    fi
  done
'
echo "build inner exit $?"
if [[ ${RECORD:-0} == 1 ]]; then
  R=$OUT/record; mkdir -p $R/src; cp $OUT/HEAD $R/UPSTREAM
  cp -r $F/src/c2/Solver_Examples $R/src/
  apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash $S2/round2/scripts/inner2.sh "$R" PODFoam_Debug "$VER" "$RC" shipped recording
  echo "record inner exit $?"
  /gscratch/syome/conda/s4f/bin/python3 $S2/round2/scripts/compare2.py "$R" PODFoam_Debug "$VER" > $R/summary.txt 2>&1
  /gscratch/syome/conda/s4f/bin/python3 - "$R" "$S2/round2/runs/PODFoam_Debug-8-shipped-25088384" <<'PY'
import sys, json
from pathlib import Path
import numpy as np
r, ref = Path(sys.argv[1]), Path(sys.argv[2])
def mats(c):
    out = {}
    for p in sorted(c.glob('snapshots-*.npz')):
        with np.load(p) as z:
            for k in 'uvw': out[f'{p.name}:{k}'] = z[k]
    return out
new = mats(r/'case-recording'); copy = mats(ref/'case-copy'); rec = mats(ref/'case-recording') if (ref/'case-recording').exists() else {}
eq = {k: bool(a.shape[1] > 1 and np.array_equal(a[:, 0], a[:, 1])) for k, a in new.items()}
same_copy = {k: bool(k in copy and copy[k].shape == a.shape and np.array_equal(copy[k], a)) for k, a in new.items()}
res = dict(matrices=len(new), col0_equals_col1=sum(eq.values()), equal_to_r2_python_copy_run=sum(same_copy.values()),
           r2_copy_matrices=len(copy), exit=(r/'case-recording/exit-status').read_text().strip())
print('RECORD', json.dumps(res)); (r/'record-check.json').write_text(json.dumps(dict(res, per_matrix_col0_equals_col1=eq, per_matrix_equal_copy=same_copy), indent=1))
PY
fi
echo done
