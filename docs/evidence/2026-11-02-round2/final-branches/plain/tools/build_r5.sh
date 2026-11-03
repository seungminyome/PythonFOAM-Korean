#!/bin/bash
# Rebuild r4/pr-observer's 11 commits as r5 commits: same trees except the five
# rewritten .md files, each placed in the commit that introduces or changes it.
# Author name, e-mail and date are kept; the committer is Seungmin Yome, now.
# Usage: build_r5.sh   (prints "i r4 r5" per commit; creates no branch)
set -euo pipefail
G=/cluster/medbow/gscratch/syome/github_repos
W=$G/pod-versions-20261030
D=$W/r4/plain
R=$G/PythonFOAM
export GIT_INDEX_FILE=$D/tmp-index
rm -f "$GIT_INDEX_FILE"
git() { command git -C "$R" "$@"; }

blob() { git hash-object -w "$1"; }
V=Solver_Examples/PODFoam/validation/README.md
H=Solver_Examples/PODFoam/HOOKS.md
L=Solver_Examples/PODFoam/llm_demo/README.md
C=Solver_Examples/PODFoam/llm_demo/hpc/README.md
B_VAL=$(blob $D/r5docs/validation_README.md)
B_HOOKS=$(blob $D/r5docs/HOOKS.md)
B_LLM5=$(blob $D/r5docs/llm_README_e05.md)
B_LLM6=$(blob $D/r5docs/llm_README_6e4.md)
B_HPC=$(blob $D/r5docs/hpc_README.md)
B_RFIX=$(blob $D/r5docs/README_fix.md)
B_ROBS=$(blob $D/r5docs/README_obs.md)

# r4 blobs each replaced file must have (from the r4docs copies)
expect() { # commit path r4doc
  local have want
  have=$(git rev-parse "$1:$2")
  want=$(git hash-object "$D/r4docs/$3")
  [ "$have" = "$want" ] || { echo "r4 $1:$2 is not r4docs/$3" >&2; exit 1; }
}

parent=6fde8698071b56f913c5e92c647f22ab38b26466
i=0
for c in $(git rev-list --reverse 6fde869..r4/pr-observer); do
  i=$((i+1))
  git read-tree "$c"
  set_file() { git update-index --cacheinfo 100644,"$1","$2"; }
  if [ $i -ge 6 ]; then expect $c $V validation_README.md; set_file $B_VAL $V; fi
  if [ $i -ge 7 ] && [ $i -le 10 ]; then expect $c README.md README_fix.md; set_file $B_RFIX README.md; fi
  if [ $i -eq 11 ]; then expect $c README.md README_obs.md; set_file $B_ROBS README.md; fi
  if [ $i -ge 8 ]; then expect $c $H HOOKS.md; set_file $B_HOOKS $H; fi
  if [ $i -eq 9 ]; then expect $c $L llm_README_e05.md; set_file $B_LLM5 $L; fi
  if [ $i -ge 10 ]; then expect $c $L llm_README_6e4.md; set_file $B_LLM6 $L; expect $c $C hpc_README.md; set_file $B_HPC $C; fi
  tree=$(git write-tree)
  # reuse the existing r5 commit when its tree, parent and message are unchanged
  if git rev-parse -q --verify r5/pr-observer >/dev/null; then
    old=$(git rev-list --reverse 6fde869..r5/pr-observer | sed -n "${i}p")
    if [ -n "$old" ] && [ "$(git rev-parse $old^{tree})" = "$tree" ] && [ "$(git rev-parse $old^)" = "$parent" ] \
       && cmp -s <(git log -1 --format=%B $old) <(git log -1 --format=%B $old | head -0; cat "$D/msgs/c$i"; echo); then
      echo "$i $c $old"; parent=$old; continue
    fi
  fi
  an=$(git log -1 --format=%an $c); ae=$(git log -1 --format=%ae $c); ad=$(git log -1 --format=%ad --date=raw $c)
  new=$(GIT_AUTHOR_NAME="$an" GIT_AUTHOR_EMAIL="$ae" GIT_AUTHOR_DATE="$ad" \
        GIT_COMMITTER_NAME="Seungmin Yome" GIT_COMMITTER_EMAIL=wab8131028@gmail.com \
        command git -C "$R" -c user.name="Seungmin Yome" -c user.email=wab8131028@gmail.com \
        commit-tree "$tree" -p "$parent" -F "$D/msgs/c$i")
  echo "$i $c $new"
  parent=$new
done
rm -f "$GIT_INDEX_FILE"
