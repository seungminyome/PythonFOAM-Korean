#!/bin/bash
# Rebuild r12/pr-observer's commits 6 to 11 as r13 commits with git commit-tree; commits 1 to 5 are kept as they are
# (their trees and messages do not change in round 12, so r13/pr-fix and r13/pr-observer share them with r12).
# Trees: r12's, with the round-12 docs from pr/r13docs/ placed in the commit that introduces or changes each doc.
# Messages: pr/msgs/c6..c11 (c7 changed). Author name, e-mail and date are r12's. Committer: Seungmin Yome, at BASE+i s.
# Usage: build_r13.sh BASE_EPOCH   (prints "i r12 r13"; creates no branch)
set -euo pipefail
G=/cluster/medbow/gscratch/syome/github_repos
D=$G/pod-versions-20261030/final/r13/fix/pr
R=$G/PythonFOAM
BASE=${1:?BASE_EPOCH}
TZ_OFF=-0700
export GIT_INDEX_FILE=$D/tmp-index
rm -f "$GIT_INDEX_FILE"
git() { command git -C "$R" "$@"; }
V=Solver_Examples/PODFoam/validation/README.md
H=Solver_Examples/PODFoam/HOOKS.md
L=Solver_Examples/PODFoam/llm_demo/README.md
C=Solver_Examples/PODFoam/llm_demo/hpc/README.md
blob() { git hash-object -w "$1"; }
B_VAL=$(blob $D/r13docs/validation_README.md)
B_HOOKS=$(blob $D/r13docs/HOOKS.md)
B_LLM9=$(blob $D/r13docs/llm_README_c9.md)
B_LLM10=$(blob $D/r13docs/llm_README_c10.md)
B_HPC=$(blob $D/r13docs/hpc_README.md)
B_RFIX=$(blob $D/r13docs/README_fix.md)
B_ROBS=$(blob $D/r13docs/README_obs.md)
expect() { # commit path r12doc: each replaced path must hold the r12 blob
  local have want
  have=$(git rev-parse "$1:$2")
  want=$(git hash-object "$D/r12docs/$3")
  [ "$have" = "$want" ] || { echo "r12 $1:$2 is not r12docs/$3" >&2; exit 1; }
}
set_file() { git update-index --cacheinfo 100644,"$1","$2"; }
i=0
for c in $(git rev-list --reverse 6fde869..r12/pr-observer); do
  i=$((i+1))
  if [ $i -le 5 ]; then
    cmp -s <(git cat-file commit "$c" | sed '1,/^$/d') "$D/msgs/c$i" || { echo "c$i message changed; it cannot be kept" >&2; exit 1; }
    echo "$i $c $c kept"; parent=$c; continue
  fi
  git read-tree "$c"
  if [ $i -ge 6 ]; then expect $c $V validation_README.md; set_file $B_VAL $V; fi
  if [ $i -ge 7 ] && [ $i -le 10 ]; then expect $c README.md README_fix.md; set_file $B_RFIX README.md; fi
  if [ $i -eq 11 ]; then expect $c README.md README_obs.md; set_file $B_ROBS README.md; fi
  if [ $i -ge 8 ]; then expect $c $H HOOKS.md; set_file $B_HOOKS $H; fi
  if [ $i -eq 9 ]; then expect $c $L llm_README_c9.md; set_file $B_LLM9 $L; fi
  if [ $i -ge 10 ]; then expect $c $L llm_README_c10.md; set_file $B_LLM10 $L; expect $c $C hpc_README.md; set_file $B_HPC $C; fi
  tree=$(git write-tree)
  an=$(git log -1 --format=%an $c); ae=$(git log -1 --format=%ae $c); ad=$(git log -1 --format=%ad --date=raw $c)
  new=$(GIT_AUTHOR_NAME="$an" GIT_AUTHOR_EMAIL="$ae" GIT_AUTHOR_DATE="$ad" \
        GIT_COMMITTER_NAME="Seungmin Yome" GIT_COMMITTER_EMAIL=wab8131028@gmail.com \
        GIT_COMMITTER_DATE="$((BASE + i)) $TZ_OFF" \
        command git -C "$R" -c user.name="Seungmin Yome" -c user.email=wab8131028@gmail.com \
        commit-tree "$tree" -p "$parent" -F "$D/msgs/c$i")
  echo "$i $c $new"
  parent=$new
done
rm -f "$GIT_INDEX_FILE"
