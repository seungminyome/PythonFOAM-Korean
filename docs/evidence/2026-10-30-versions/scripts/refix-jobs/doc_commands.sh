#!/bin/bash
# Runs the "observer with no model" commands of llm_demo/README.md in a fresh copy of the PR tree, in one version's image.
# usage: doc_commands.sh VERSION [IMAGE]
VER=$1
G=/cluster/medbow/gscratch/syome/github_repos; W=$G/pod-versions-20261030
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown $VER"; exit 2;;
esac
SIF=${2:-$SIF}
module load apptainer
OUT=$(mktemp -d "$W/pr/refix/doc-runs/$VER-XXXXXX")
mkdir "$OUT/PythonFOAM"
git -C $W/pr/wt/n6 archive HEAD | tar -x -C "$OUT/PythonFOAM"
export OPENFOAM_BASHRC=$RC POD_OPENFOAM_VERSION=$VER PYTHON=/gscratch/syome/conda/s4f/bin/python3 OUT
echo "node $(hostname) version $VER image $SIF copy of $(git -C $W/pr/wt/n6 rev-parse --short HEAD) in $OUT"
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash <<'INNER'
source "$OPENFOAM_BASHRC" > /dev/null 2>&1
export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
cd "$OUT/PythonFOAM/Solver_Examples/PODFoam" || exit 1
./validation/run_v2106.sh > "$OUT/validation.log" 2>&1; echo "validation exit $?"; tail -1 "$OUT/validation.log"
run=$(sed -n 's/^PASS: //p' "$OUT/validation.log"); [[ -n $run ]] || exit 1
set -x
case=$run/observer; mkdir $case
cp -r $run/fixed-pod/{0,constant,system} $case/
cp llm_demo/{python_module,bounded_ipc,llm_client,pod_image,readable_image,readable_request}.py $case/
cp validation/python_module.py $case/pod_svd.py
LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 $run/bin/PODFoam -case $case > $case/log.PODFoam
echo "observer exit $?"
ls $case/llm_observation/step-000005
set +x
tail -3 $case/log.PODFoam
"$PYTHON" - "$run" <<'PY'
import hashlib, json, re, sys
from pathlib import Path
run = Path(sys.argv[1]); case = run/'observer'; ref = run/'fixed-pod'
result = json.loads((case/'llm_result.json').read_text())
lines = (case/'telemetry.jsonl').read_text().splitlines()
frame = case/'llm_observation/step-000005'
print('status', result['status'], 'telemetry lines', len(lines), 'frame files', sorted(p.name for p in frame.iterdir()),
      'errors file', (case/'llm_errors.jsonl').exists())
compared = same = 0
for folder in ref.iterdir():
    if folder.is_dir() and re.fullmatch(r'[0-9.eE+-]+', folder.name) and float(folder.name) > 0:
        for field in folder.iterdir():
            if field.is_file():
                compared += 1
                same += field.read_bytes() == (case/folder.name/field.name).read_bytes()
print(f'written files equal to fixed-pod: {same} of {compared}')
ok = result['status'] == 'disabled' and len(lines) == 10 and same == compared > 0 and (frame/'readable-metadata.json').exists()
print('DOC COMMANDS', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
PY
INNER
status=$?
echo "exit $status"
exit $status
