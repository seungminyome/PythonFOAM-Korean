#!/bin/bash
# Final checks of r5/pr-fix and r5/pr-observer against r4 (read-only).
set -uo pipefail
G=/cluster/medbow/gscratch/syome/github_repos
D=$G/pod-versions-20261030/r4/plain
R=$G/PythonFOAM
P=/gscratch/syome/conda/s4f/bin/python3
cd "$R" || exit 1
fail=0
MD5="README.md Solver_Examples/PODFoam/HOOKS.md Solver_Examples/PODFoam/validation/README.md Solver_Examples/PODFoam/llm_demo/README.md Solver_Examples/PODFoam/llm_demo/hpc/README.md"

echo "== per-commit pairs (r4 -> r5): non-.md diff, tree, files changed by the commit"
paste <(git rev-list --reverse 6fde869..r4/pr-observer) <(git rev-list --reverse 6fde869..r5/pr-observer) | nl -w2 -s' ' |
while read -r i a b; do
  nd=$(git diff "$a" "$b" -- ':!*.md' | wc -c)
  same=$([ "$(git rev-parse "$a^{tree}")" = "$(git rev-parse "$b^{tree}")" ] && echo "same tree" || echo "md differs: $(git diff --name-only "$a" "$b" | tr '\n' ' ')")
  fc=$([ "$(git diff --name-only "$a^" "$a")" = "$(git diff --name-only "$b^" "$b")" ] && echo "same files" || echo "FILES DIFFER")
  echo "c$i ${a:0:7} -> ${b:0:7}  non-md diff bytes $nd; $fc; $same"
  [ "$nd" = 0 ] && [ "$fc" = "same files" ] || echo FAIL
done
echo "== r4/pr-fix vs r5/pr-fix: $(git diff --name-only r4/pr-fix r5/pr-fix | tr '\n' ' ')"
echo "== r4/pr-observer vs r5/pr-observer: $(git diff --name-only r4/pr-observer r5/pr-observer | tr '\n' ' ')"
extra=$(git diff --name-only r4/pr-observer r5/pr-observer | grep -vxF -f <(tr ' ' '\n' <<<"$MD5") | wc -l)
echo "   files outside the five docs: $extra"; [ "$extra" = 0 ] || fail=1
echo "== r5/pr-fix is r5/pr-observer~4: $([ "$(git rev-parse r5/pr-observer~4)" = "$(git rev-parse r5/pr-fix)" ] && echo yes || echo NO)"
echo "== base: $(git merge-base 6fde869 r5/pr-observer)"
echo "== messages"
mkdir -p "$D/counts/msgs-final"; rm -f "$D/counts/msgs-final"/c*
i=0; for c in $(git rev-list --reverse 6fde869..r5/pr-observer); do i=$((i+1)); git log -1 --format=%B "$c" > "$D/counts/msgs-final/c$i"; done
$P -I "$D/../fix/check_msg.py" "$D"/counts/msgs-final/c{1..11} || fail=1
echo "   author/committer: $(git log --format='%an <%ae>|%cn <%ce>' 6fde869..r5/pr-observer | sort -u)"
echo "   '<earlier-model-name>' in messages $(git log --format=%B 6fde869..r5/pr-observer | grep -ci <earlier-model-name>), in tree $(git grep -il <earlier-model-name> r5/pr-observer | wc -l), in diff $(git diff 6fde869 r5/pr-observer | grep -ci <earlier-model-name>)"
echo "   'upstream' in messages $(git log --format=%B 6fde869..r5/pr-observer | grep -ci upstream), in the five docs $(git grep -i upstream r5/pr-observer -- $MD5 | wc -l)"
echo "   trailer lines $(git log --format=%B 6fde869..r5/pr-observer | grep -c '^Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>$') of $(git log --format=%B 6fde869..r5/pr-observer | grep -c 'Co-Authored-By')"
git diff --check r4/pr-observer r5/pr-observer && echo "   diff --check clean"
echo "== links and quoted references at c6..c11"
i=0; for c in $(git rev-list --reverse 6fde869..r5/pr-observer); do i=$((i+1)); [ $i -lt 6 ] && continue
  $P -I "$D/tools/check_links.py" "$R" "$c" > "$D/counts/links_c$i.txt"; e=$?
  echo "c$i ${c:0:7} exit $e, ok $(grep -c '^ok' "$D/counts/links_c$i.txt"), broken $(grep -c BROKEN "$D/counts/links_c$i.txt")"; [ $e = 0 ] || fail=1
done
echo "== numbers kept (r4 doc -> r5 doc, as committed)"
num() { git show "$1" > "$D/counts/r4.tmp"; git show "$2" > "$D/counts/r5.tmp"; $P -I "$D/tools/numbers_kept.py" "$D/counts/r4.tmp" "$D/counts/r5.tmp" | head -1 | sed "s|^[^:]*:|$3:|"; }
num 8376b00:Solver_Examples/PODFoam/validation/README.md r5/pr-observer:Solver_Examples/PODFoam/validation/README.md validation/README.md
num r4/pr-fix:README.md r5/pr-fix:README.md README.md@fix
num r4/pr-observer:README.md r5/pr-observer:README.md README.md@observer
num r4/pr-observer:Solver_Examples/PODFoam/HOOKS.md r5/pr-observer:Solver_Examples/PODFoam/HOOKS.md HOOKS.md
num e05643e:Solver_Examples/PODFoam/llm_demo/README.md r5/pr-observer~2:Solver_Examples/PODFoam/llm_demo/README.md llm_demo/README.md@llm_demo
num r4/pr-observer:Solver_Examples/PODFoam/llm_demo/README.md r5/pr-observer:Solver_Examples/PODFoam/llm_demo/README.md llm_demo/README.md@hpc
num r4/pr-observer:Solver_Examples/PODFoam/llm_demo/hpc/README.md r5/pr-observer:Solver_Examples/PODFoam/llm_demo/hpc/README.md llm_demo/hpc/README.md
rm -f "$D/counts/r4.tmp" "$D/counts/r5.tmp"
echo "== committed docs equal the r5docs files"
for pair in "r5/pr-observer:Solver_Examples/PODFoam/validation/README.md validation_README.md" "r5/pr-observer:Solver_Examples/PODFoam/HOOKS.md HOOKS.md" "r5/pr-observer~2:Solver_Examples/PODFoam/llm_demo/README.md llm_README_e05.md" "r5/pr-observer:Solver_Examples/PODFoam/llm_demo/README.md llm_README_6e4.md" "r5/pr-observer:Solver_Examples/PODFoam/llm_demo/hpc/README.md hpc_README.md" "r5/pr-fix:README.md README_fix.md" "r5/pr-observer:README.md README_obs.md"; do
  set -- $pair; cmp -s <(git show "$1") "$D/r5docs/$2" && echo "   $2 = $1" || { echo "   $2 DIFFERS from $1"; fail=1; }
done
echo "OVERALL $([ $fail = 0 ] && echo PASS || echo FAIL)"
