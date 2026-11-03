#!/bin/bash
# export.sh <repo worktree> <commit> <label>: git archive of <commit> into src/<label> with a HEAD file
set -euo pipefail
I=/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r4/integrate
d=$I/src/$3; rm -rf "$d"; mkdir -p "$d"
git -C "$1" archive "$2" | tar -x -C "$d"
git -C "$1" rev-parse "$2" > "$d/HEAD"; touch "$d/HEAD"
echo "$d $(cat $d/HEAD)"
