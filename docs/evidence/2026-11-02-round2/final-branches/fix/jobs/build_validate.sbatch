#!/bin/bash
#SBATCH --job-name=r4f-bv
#SBATCH --account=me5475
#SBATCH --partition=teton,non-investor,wildiris,mb
#SBATCH --exclude=t527
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --chdir=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix
#SBATCH --output=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/fix/logs/bv-%x-%j.out
# Environment: VER (v2012, v2106, v2212, 8). Builds PODFoam from the exports of every r4/pr-fix and r4/pr-observer
# commit (src/<n>), then runs validation/run.sh at c6, c7 (fix tip), hooks and obs (observer tip).
set -uo pipefail
W=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030; A=$W/r4/fix
case $VER in
  v2012) SIF=$W/images/of-v2012-dev.sif; RC=/usr/lib/openfoam/openfoam2012/etc/bashrc;;
  v2106) SIF=$W/images/of-v2106-dev.sif; RC=/usr/lib/openfoam/openfoam2106/etc/bashrc;;
  v2212) SIF=/cluster/medbow/gscratch/syome/s4f/of2212.sif; RC=/usr/lib/openfoam/openfoam2212/etc/bashrc;;
  8)     SIF=$W/images/of-8.sif; RC=/opt/openfoam8/etc/bashrc;;
  *) echo "unknown $VER"; exit 2;;
esac
module load apptainer
export PYTHON=/gscratch/syome/conda/s4f/bin/python3 OPENFOAM_BASHRC=$RC POD_OPENFOAM_VERSION=$VER
echo "job $SLURM_JOB_ID node $(hostname) version $VER"
for n in ${BUILDS:-c1 c2 c3 c4 c5 c6 c7 hooks llm hpc obs}; do
  ROOT=$A/src/$n
  OUT=$A/builds/$VER-$n-$SLURM_JOB_ID; mkdir -p $OUT/bin $OUT/build/Make
  export OUT ROOT
  apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash -c '
    set --; set +e; source "$OPENFOAM_BASHRC" > /dev/null 2>&1; set -e
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
    export FOAM_USER_APPBIN=$OUT/bin
    export PYTHON_INCLUDE_PATH=$("$PYTHON" -c "import sysconfig; print(sysconfig.get_path(\"include\"))")
    export NUMPY_INCLUDE_PATH=$("$PYTHON" -c "import numpy; print(numpy.get_include())")
    export PYTHON_LIB_PATH=$("$PYTHON" -c "import sysconfig; print(sysconfig.get_config_var(\"LIBDIR\"))")
    export PYTHON_LIB_NAME=lpython$("$PYTHON" -c "import sysconfig; print(sysconfig.get_config_var(\"LDVERSION\"))")
    src=$ROOT/Solver_Examples/PODFoam
    cp "$src/"*.H "$src/PODFoam.C" "$OUT/build/"
    cp "$src/Make/options" "$src/Make/files" "$OUT/build/Make/"
    wmake "$OUT/build" > "$OUT/log.build" 2>&1
    ldd "$OUT/bin/PODFoam" > "$OUT/ldd.txt"
    ! grep -q "not found" "$OUT/ldd.txt"
  '
  status=$?
  echo "BUILD $n $(cut -c1-7 $ROOT/HEAD) $VER exit $status warnings $(grep -c -i 'warning' $OUT/log.build)"
  if [[ $status != 0 ]]; then grep -n -E "error|Error" "$OUT/log.build" | head -30 | cut -c1-240; fi
done
for n in ${VALS:-c6 c7 hooks obs}; do
  ROOT=$A/src/$n
  export POD_WORKSPACE=$A/runs/$VER-$n; mkdir -p "$POD_WORKSPACE"
  apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash -c '
    set --; set +e; source "$OPENFOAM_BASHRC" > /dev/null 2>&1; set -e
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
    cd "'"$ROOT"'/Solver_Examples/PODFoam" && ./validation/run.sh'
  status=$?
  run=$(ls -td $POD_WORKSPACE/pod-$VER.* 2>/dev/null | head -1)
  echo "VALIDATION $n $(cut -c1-7 $ROOT/HEAD) $VER exit $status run $run"
  if [[ $status != 0 ]]; then tail -5 "$run/fixed-pod/log.PODFoam" 2>/dev/null | cut -c1-200; tail -3 "$run/log.build" 2>/dev/null | cut -c1-200; fi
  echo "  staged cases: $(ls -d $run/*/ 2>/dev/null | xargs -n1 basename | grep -E 'pimple|pod' | tr '\n' ' ')"
  if [[ $n == obs && $status == 0 ]]; then mkdir -p $A/ref; ln -sfn "$run" $A/ref/$VER; echo "  reference link $A/ref/$VER -> $run"; fi
done
# --resume on the obs run (the renamed script's resume path) and --baseline on a fresh run, obs tree only
ROOT=$A/src/obs; export POD_WORKSPACE=$A/runs/$VER-obs
run=$(ls -td $POD_WORKSPACE/pod-$VER.* | head -1)
apptainer exec --bind /cluster/medbow/gscratch "$SIF" bash -c '
    set --; set +e; source "$OPENFOAM_BASHRC" > /dev/null 2>&1; set -e
    export LD_LIBRARY_PATH=$(dirname "$PYTHON")/../lib:$LD_LIBRARY_PATH
    cd "'"$ROOT"'/Solver_Examples/PODFoam" && ./validation/run.sh --baseline --resume "'"$run"'"' > $A/runs/$VER-obs/resume-baseline.log 2>&1
echo "RESUME+BASELINE obs $VER exit $? $(tail -1 $A/runs/$VER-obs/resume-baseline.log | cut -c1-120) baseline-exit $(cat $run/baseline-pimple/exit-status 2>/dev/null) staged: $(ls -d $run/*/ | xargs -n1 basename | grep -E 'pimple|pod' | tr '\n' ' ')"
echo "export status: $(cd $A/src/obs && find . -newer HEAD -type f | grep -v '^./Solver_Examples/PODFoam/validation/runs' | wc -l) files newer than HEAD outside validation/runs"
echo done
