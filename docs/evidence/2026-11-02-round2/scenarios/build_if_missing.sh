#!/bin/bash
# same as build_inner.sh, but a build whose binary exists is kept (the v2012/v2212 binaries used by jobs 25080002/25080003)
R=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/scenarios
VER=$1
source $R/env.sh
for v in fork upstream; do
  b=$R/build/$VER/$v
  if [ -x $b/bin/PODFoam ]; then echo "$VER $v build kept $(ls -la $b/bin/PODFoam)"; continue; fi
  mkdir -p $b/bin $b/src
  cp -r $R/src/$v/Solver_Examples/PODFoam/. $b/src/
  export FOAM_USER_APPBIN=$b/bin
  (cd $b/src && wmake > $b/log.build 2>&1); echo "$VER $v build exit $? $(ls -la $b/bin)"
done
