#!/bin/bash
# Rebuild r5/pr-observer's 11 commits as r6 commits with git commit-tree.
# Trees: r5's, with the fixed docs from r6docs/ placed in the commit that introduces
# or changes each doc. Messages: msgs/c1..c11. Author name, e-mail and date are r5's,
# except commits 10 and 11, whose author dates follow commit 9's (14:51:08) so that
# author dates increase along the series. Committer: Seungmin Yome, at BASE+i seconds.
# Usage: build_r6.sh BASE_EPOCH   (prints "i r5 r6"; creates no branch)
# The same BASE_EPOCH gives the same hashes.
set -euo pipefail
G=/cluster/medbow/gscratch/syome/github_repos
D=$G/pod-versions-20261030/r5/pr
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
B_VAL=$(blob $D/r6docs/validation_README.md)
B_HOOKS=$(blob $D/r6docs/HOOKS.md)
B_LLM9=$(blob $D/r6docs/llm_README_c9.md)
B_LLM10=$(blob $D/r6docs/llm_README_c10.md)
B_HPC=$(blob $D/r6docs/hpc_README.md)
B_RFIX=$(blob $D/r6docs/README_fix.md)
B_ROBS=$(blob $D/r6docs/README_obs.md)

# each replaced path must hold the r5 blob that r5docs/ records
expect() { # commit path r5doc
  local have want
  have=$(git rev-parse "$1:$2")
  want=$(git hash-object "$D/r5docs/$3")
  [ "$have" = "$want" ] || { echo "r5 $1:$2 is not r5docs/$3" >&2; exit 1; }
}
set_file() { git update-index --cacheinfo 100644,"$1","$2"; } # blob path

# author dates of commits 10 and 11 (raw), after commit 9's 14:51:08 -0700
AD10="$(date -d '2026-11-02 14:51:17 -0700' +%s) -0700"
AD11="$(date -d '2026-11-02 14:51:18 -0700' +%s) -0700"

parent=6fde8698071b56f913c5e92c647f22ab38b26466
i=0
for c in $(git rev-list --reverse 6fde869..r5/pr-observer); do
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
  [ $i -eq 10 ] && ad=$AD10
  [ $i -eq 11 ] && ad=$AD11
  new=$(GIT_AUTHOR_NAME="$an" GIT_AUTHOR_EMAIL="$ae" GIT_AUTHOR_DATE="$ad" \
        GIT_COMMITTER_NAME="Seungmin Yome" GIT_COMMITTER_EMAIL=wab8131028@gmail.com \
        GIT_COMMITTER_DATE="$((BASE + i)) $TZ_OFF" \
        command git -C "$R" -c user.name="Seungmin Yome" -c user.email=wab8131028@gmail.com \
        commit-tree "$tree" -p "$parent" -F "$D/msgs/c$i")
  echo "$i $c $new"
  parent=$new
done
rm -f "$GIT_INDEX_FILE"
