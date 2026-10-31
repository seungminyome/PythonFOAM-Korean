#!/bin/bash
R=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/pr/refix/cpp
VER=$1
source $R/env.sh
for v in fork; do
  b=$R/build/$VER/$v; mkdir -p $b/bin $b/src
  cp -r $R/src/$v/Solver_Examples/PODFoam/. $b/src/
  export FOAM_USER_APPBIN=$b/bin
  (cd $b/src && wmake > $b/log.build 2>&1); echo "$VER $v build exit $? $(ls -la $b/bin)"
done
