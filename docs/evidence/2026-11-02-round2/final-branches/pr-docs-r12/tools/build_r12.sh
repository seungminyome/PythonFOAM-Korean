#!/bin/bash
# Rebuild r11/pr-observer's 11 commits as r12 commits with git commit-tree.
# Trees: r11's, with the round-11 docs from pr/r12docs/ placed in the commit that introduces
# or changes each doc. Messages: pr/msgs/c1..c11. Author name, e-mail and date are r11's.
# Committer: Seungmin Yome, at BASE+i seconds.
# Usage: build_r12.sh BASE_EPOCH   (prints "i r11 r12"; creates no branch)
set -euo pipefail
G=/cluster/medbow/gscratch/syome/github_repos
D=$G/pod-versions-20261030/loop/r11/fix/pr
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
B_VAL=$(blob $D/r12docs/validation_README.md)
B_HOOKS=$(blob $D/r12docs/HOOKS.md)
B_LLM9=$(blob $D/r12docs/llm_README_c9.md)
B_LLM10=$(blob $D/r12docs/llm_README_c10.md)
B_HPC=$(blob $D/r12docs/hpc_README.md)
B_RFIX=$(blob $D/r12docs/README_fix.md)
B_ROBS=$(blob $D/r12docs/README_obs.md)
expect() { # commit path r11doc: each replaced path must hold the r11 blob
  local have want
  have=$(git rev-parse "$1:$2")
  want=$(git hash-object "$D/r11docs/$3")
  [ "$have" = "$want" ] || { echo "r11 $1:$2 is not r11docs/$3" >&2; exit 1; }
}
set_file() { git update-index --cacheinfo 100644,"$1","$2"; }
parent=6fde8698071b56f913c5e92c647f22ab38b26466
i=0
for c in $(git rev-list --reverse 6fde869..r11/pr-observer); do
  i=$((i+1))
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
