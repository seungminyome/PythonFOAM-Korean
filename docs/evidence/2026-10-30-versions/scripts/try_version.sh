#!/bin/bash
# usage: try_version.sh VERSION [CODE_ROOT]  -- runs validation/run_v2106.sh for one OpenFOAM version inside its image
VER=$1; ROOT=${2:-/cluster/medbow/gscratch/syome/github_repos/PythonFOAM-compat}
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown $VER"; exit 2;;
esac
module load apptainer
export PYTHON=/gscratch/syome/conda/s4f/bin/python3 OPENFOAM_BASHRC=$RC POD_OPENFOAM_VERSION=$VER
export POD_WORKSPACE=$W/runs/$VER; mkdir -p "$POD_WORKSPACE"
echo "node $(hostname) version $VER code $ROOT $(git -C $ROOT rev-parse --short HEAD) $(git -C $ROOT status --short | wc -l) changed"
apptainer exec "$SIF" bash -c '
  set +e; source "$OPENFOAM_BASHRC" > /dev/null 2>&1; set -e
  export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
  cd "'"$ROOT"'/Solver_Examples/PODFoam" && ./validation/run_v2106.sh'
status=$?
run=$(ls -td $POD_WORKSPACE/pod-$VER.* | head -1)
echo "exit $status run $run"
if [[ $status != 0 ]]; then grep -n -E "error|Error" "$run/log.build" 2>/dev/null | head -40 | cut -c1-200; tail -5 "$run/log.build" 2>/dev/null | cut -c1-200; fi
exit $status
