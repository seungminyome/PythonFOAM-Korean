#!/bin/bash
# Runs inside one OpenFOAM image. Args: VER OUT SRCRUN RC
# For each solver build, runs the stabilised case for 2 time steps with p and pFinal (and U and UFinal)
# given different *solver names*, so the log line itself names the dictionary that was used.
VER=$1 OUT=$2 SRCRUN=$3 RC=$4
set --
source "$RC" >/dev/null 2>&1 || true
PY=/gscratch/syome/conda/s4f/bin/python3
export LD_LIBRARY_PATH=/gscratch/syome/conda/s4f/lib:$LD_LIBRARY_PATH
export PYTHONHOME=/gscratch/syome/conda/s4f PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
echo "WM_PROJECT_VERSION=$WM_PROJECT_VERSION WM_PROJECT_DIR=$WM_PROJECT_DIR pimpleFoam=$(command -v pimpleFoam)" | tee "$OUT/env.txt"
stage() { # stage NAME NOUTER
    local c=$OUT/case-$1
    rm -rf "$c"; mkdir -p "$c"
    cp -r "$SRCRUN/case-fork/0" "$SRCRUN/case-fork/constant" "$SRCRUN/case-fork/system" "$c/"
    cp "$SRCRUN/case-fork/python_module.py" "$c/"
    sed -i 's/^endTime .*/endTime 2e-7;/; s/^writeInterval .*/writeInterval 2;/' "$c/system/controlDict"
    $PY - "$c/system/fvSolution" "$2" <<'PYEOF'
import re, sys
p, nouter = sys.argv[1], sys.argv[2]
t = open(p).read()
solvers = '''solvers
{
    p
    {
        solver          PCG;
        preconditioner  DIC;
        tolerance       1e-06;
        relTol          0.1;
    }

    pFinal
    {
        solver          GAMG;
        smoother        DICGaussSeidel;
        tolerance       1e-08;
        relTol          0;
    }

    "(U|k|epsilon|nuTilda|omega)"
    {
        solver          smoothSolver;
        smoother        symGaussSeidel;
        tolerance       1e-05;
        relTol          0.1;
    }

    "(U|k|nuTilda)Final"
    {
        solver          PBiCGStab;
        preconditioner  DILU;
        tolerance       1e-05;
        relTol          0;
    }
}
'''
t, n = re.subn(r'solvers\n\{.*?\n\}\n', solvers, t, count=1, flags=re.S)
assert n == 1
t, n = re.subn(r'nOuterCorrectors\s+\d+;', 'nOuterCorrectors %s;' % nouter, t)
assert n == 1
open(p, 'w').write(t)
PYEOF
}
run() { # run NAME EXE
    local c=$OUT/case-$1 status=0
    (cd "$c" && env MPLCONFIGDIR=$c/mpl "$2" -case "$c" > log.solver 2>&1) || status=$?
    printf '%s\n' "$status" > "$c/exit-status"
    echo "$1 exit $status  p-solves: $(grep -c 'Solving for p' "$c/log.solver")  $(grep -o '^[A-Za-z]*:  Solving for p' "$c/log.solver" | sort | uniq -c | tr '\n' ';')"
}
for nouter in 1 2; do
    stage pimpleFoam-n$nouter $nouter;  run pimpleFoam-n$nouter pimpleFoam
    stage fork-n$nouter $nouter;        run fork-n$nouter "$SRCRUN/bin-fork/PODFoam"
    stage upstream-n$nouter $nouter;    run upstream-n$nouter "$SRCRUN/bin-upstream/PODFoam"
    if [[ -x $SRCRUN/bin-fork-plainp/PODFoam ]]; then
        stage fork-plainp-n$nouter $nouter; run fork-plainp-n$nouter "$SRCRUN/bin-fork-plainp/PODFoam"
    fi
done
