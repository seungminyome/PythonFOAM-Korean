#!/bin/bash
# Runs inside an OpenFOAM image. Arguments: OUT VER RC DIM VARIANTS...
# Stages the matrix case (job 24950783's copy, 2D or 3D), swaps system/fvSolution for dicts/fvSolution.<variant>,
# runs plain pimpleFoam for 100 steps from t = 0.1 s and writes 0.1005.
OUT=$1 VER=$2 RC=$3 DIM=$4; shift 4
set --  # the openfoam.com bashrc reads positional parameters
source "$RC" >/dev/null 2>&1 || true
R=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/of8-cause
M=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/refix/matrix/8-24950783
VARIANTS=$(cat "$OUT/variants.txt")
for V in $VARIANTS; do
    c=$OUT/$V; mkdir -p "$c"
    if [[ $DIM == 2d ]]; then for d in 0 constant system 0.1; do cp -r "$M/serial2d/$d" "$c/"; done
    else cp -r "$M/serial3d/constant" "$M/serial3d/system" "$M/serial3d/0.1" "$c/"; fi
    cp "$R/dicts/fvSolution.$V" "$c/system/fvSolution"
    sed -i 's/^application .*/application pimpleFoam;/; s/^endTime .*/endTime 0.100005;/; s/^writeInterval .*/writeInterval 1;/' "$c/system/controlDict"
    status=0
    (cd "$c" && pimpleFoam -case "$c" > log.pimpleFoam 2>&1) || status=$?
    printf '%s\n' "$status" > "$c/exit-status"
    echo "$VER $DIM $V exit $status; wrote: $(ls -d "$c"/0.1005 2>/dev/null)"
    grep -c 'Solving for p' "$c/log.pimpleFoam"
done
which pimpleFoam; echo "done"
