#!/bin/bash
# Inside the image. Arguments: RUN SRCROOT VER BASHRC. Staging follows r2/slice-3d/scripts/phase1_inner.sh
# (3D step case of job 24929629, start serial3d/0.10075, 300 steps, POD_SLICE_Z of z3, LLM_ENABLED=0, v2 frames
# every 50 steps), with validation/run.sh of the tree and the tree's validation/python_module.py as pod_svd.py.
RUN=$1 REPO=$2 VER=$3 RC=$4
set --
source "$RC" >/dev/null 2>&1 || true
set -o pipefail
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH PYTHON=$PY POD_OPENFOAM_VERSION=$VER POD_WORKSPACE=$RUN OPENFOAM_BASHRC=$RC
CASE3D=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/case3d
START=/cluster/medbow/gscratch/syome/github_repos/pod-3d-20261028/run-24929629/serial3d/0.10075
POD=$REPO/Solver_Examples/PODFoam; DEMO=$POD/llm_demo
(cd "$POD" && ./validation/run.sh > "$RUN/validation.log" 2>&1) && echo 'build + validation ran' || echo 'build + validation FAILED'
grep -E '^PASS|FAIL' "$RUN/validation.log" | tail -1
exe=$(ls -d "$RUN"/pod-$VER.*/bin/PODFoam | head -1); echo "exe=$exe"
[[ -x $exe ]] || exit 1
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
export LLM_ENABLED=0 LLM_MODE=describe LLM_IMAGE_STYLE=v2 LLM_ASYNC=1 LLM_ANALYSIS_STEP=50 LLM_ANALYSIS_EVERY=50 LLM_IMAGE_XRANGE=0,0.12 LLM_IMAGE_YRANGE=0,0.04
c=$RUN/z3; Z=0.00396875
mkdir -p "$c/0.10075"
cp -r "$CASE3D/constant" "$CASE3D/system" "$c/"
for f in U p phi; do cp "$START/$f" "$c/0.10075/"; done     # no uniform/time: the time index starts at 0
sed 's/object      turbulenceProperties;/object      momentumTransport;/' "$c/constant/turbulenceProperties" > "$c/constant/momentumTransport"
if [[ $VER != v* ]]; then sed -i '/libincompressibleTurbulenceModels/d' "$c/system/controlDict"; fi
cp "$POD/validation/python_module.py" "$c/pod_svd.py"
for f in python_module.py bounded_ipc.py llm_client.py readable_request.py readable_image.py pod_image.py; do cp "$DEMO/$f" "$c/"; done
sed -i 's/^startTime .*/startTime 0.10075;/; s/^endTime .*/endTime 0.10225;/; s/^writeInterval .*/writeInterval 50;/' "$c/system/controlDict"
printf '%s\n' "$Z" > "$c/slice-z.txt"
echo "run start $(date -u +%T)"
status=0
(cd "$c" && env MPLCONFIGDIR=$c/mpl LLM_RUN_ID=r4-slice-3d/$VER POD_SLICE_Z=$Z "$exe" -case "$c" > log.PODFoam 2>&1) || status=$?
printf '%s\n' "$status" > "$c/exit-status"; echo "z3 exit $status $(date -u +%T)"
grep -E 'POD (observer )?plane slice|No plane slice|POD mesh geometry|Python finalized|^End|FOAM FATAL|FOAM Warning' "$c/log.PODFoam" | head -8 | cut -c1-220
echo "Time lines $(grep -c '^Time = ' $c/log.PODFoam) snapshots $(grep -c 'POD snapshot accepted' $c/log.PODFoam) SVDs $(grep -c 'POD SVD returned' $c/log.PODFoam) analysis $(grep -c 'POD analysis callback returned' $c/log.PODFoam) Traceback $(grep -c Traceback $c/log.PODFoam)"
for d in "$c"/llm_observation/step-*; do echo "frame $(basename $d): $(ls $d | tr '\n' ' ')"; done
rm -f "$c/python_svd_audit.npz"
