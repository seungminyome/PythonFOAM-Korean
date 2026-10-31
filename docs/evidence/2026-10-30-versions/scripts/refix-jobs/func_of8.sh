#!/bin/bash
# OpenFOAM 8 image: a user who has sourced OpenFOAM and has the right python3 first on PATH sets nothing else.
P=/gscratch/syome/conda/s4f
source /opt/openfoam8/etc/bashrc > /dev/null 2>&1
export PATH=$P/bin:$PATH LD_LIBRARY_PATH=$P/lib:$LD_LIBRARY_PATH POD_WORKSPACE=$OUT/ws8; mkdir -p $POD_WORKSPACE
unset PYTHON OPENFOAM_BASHRC POD_OPENFOAM_VERSION
cd $OUT/PythonFOAM/Solver_Examples/PODFoam
echo "=== OpenFOAM 8 sourced, no variable set"
./validation/run_v2106.sh > $OUT/of8-validation.log 2>&1; echo "exit $?"; tail -1 $OUT/of8-validation.log | cut -c1-200
echo "baseline: exit-status $(cat $POD_WORKSPACE/pod-8.*/baseline-pimple/exit-status)"
