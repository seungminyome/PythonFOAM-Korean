#!/bin/bash
# merge_tree.sh <repo> <main commit> <PR tip>: print the tree of the fork-main merge.
# Rule (r4/integrate/NOTES.md): main's tree, every file of the PR tip taken from it
# (root README.md and .gitignore included), and validation/run_v2106.sh removed.
set -euo pipefail
repo=$1 main=$2 pr=$3
idx=$(mktemp -p /cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r5/main/tmp mergeidx.XXXXXX)
export GIT_INDEX_FILE=$idx
git -C "$repo" read-tree "$main"
git -C "$repo" ls-tree -r "$pr" | sed 's/^\([0-9]*\) blob \([0-9a-f]*\)\t/\1 \2\t/' | git -C "$repo" update-index --add --index-info
git -C "$repo" update-index --force-remove Solver_Examples/PODFoam/validation/run_v2106.sh
git -C "$repo" write-tree
rm -f "$idx"
