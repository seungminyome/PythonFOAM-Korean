#!/bin/bash
# Checks of r6/pr-fix and r6/pr-observer against r5 (read-only).
set -uo pipefail
G=/cluster/medbow/gscratch/syome/github_repos
D=$G/pod-versions-20261030/r5/pr
R=$G/PythonFOAM
P=/gscratch/syome/conda/s4f/bin/python3
cd "$R" || exit 1
fail=0
MD5="README.md Solver_Examples/PODFoam/HOOKS.md Solver_Examples/PODFoam/validation/README.md Solver_Examples/PODFoam/llm_demo/README.md Solver_Examples/PODFoam/llm_demo/hpc/README.md"

echo "== per-commit pairs (r5 -> r6): non-.md diff, tree, files changed by the commit"
paste <(git rev-list --reverse 6fde869..r5/pr-observer) <(git rev-list --reverse 6fde869..r6/pr-observer) | nl -w2 -s' ' |
while read -r i a b; do
  nd=$(git diff "$a" "$b" -- ':!*.md' | wc -c)
  same=$([ "$(git rev-parse "$a^{tree}")" = "$(git rev-parse "$b^{tree}")" ] && echo "same tree" || echo "md differs: $(git diff --name-only "$a" "$b" | tr '\n' ' ')")
  fc=$([ "$(git diff --name-only "$a^" "$a")" = "$(git diff --name-only "$b^" "$b")" ] && echo "same files" || echo "FILES DIFFER")
  echo "c$i ${a:0:7} -> ${b:0:7}  non-md diff bytes $nd; $fc; $same"
  [ "$nd" = 0 ] && [ "$fc" = "same files" ] || echo FAIL
  if [ "$i" -le 5 ] && [ "$same" != "same tree" ]; then echo "FAIL: commit $i tree changed"; fi
done | tee "$D/counts/pairs.txt"
grep -q FAIL "$D/counts/pairs.txt" && fail=1
echo "== r5/pr-fix vs r6/pr-fix: $(git diff --name-only r5/pr-fix r6/pr-fix | tr '\n' ' ')"
echo "== r5/pr-observer vs r6/pr-observer: $(git diff --name-only r5/pr-observer r6/pr-observer | tr '\n' ' ')"
extra=$(git diff --name-only r5/pr-observer r6/pr-observer | grep -vxF -f <(tr ' ' '\n' <<<"$MD5") | wc -l)
echo "   files outside the five docs: $extra"; [ "$extra" = 0 ] || fail=1
echo "== r6/pr-fix is r6/pr-observer~4: $([ "$(git rev-parse r6/pr-observer~4)" = "$(git rev-parse r6/pr-fix)" ] && echo yes || { fail=1; echo NO; })"
echo "== base: $(git merge-base 6fde869 r6/pr-observer); parents: $(git rev-list --parents 6fde869..r6/pr-observer | awk 'NF!=2' | wc -l) commits with other than one parent"
echo "== dates along the 11 commits (author | committer)"
prev_a=0; prev_c=0
while read -r h a c; do
  ok=yes
  [ "$a" -gt "$prev_a" ] || ok=NO; [ "$c" -gt "$prev_c" ] || ok=NO; [ "$c" -ge "$a" ] || ok=NO
  echo "   ${h:0:7} $(date -d @$a '+%F %T') | $(date -d @$c '+%F %T')  increasing $ok"
  [ $ok = yes ] || fail=1
  prev_a=$a; prev_c=$c
done < <(git log --reverse --format='%H %at %ct' 6fde869..r6/pr-observer)
echo "== messages"
mkdir -p "$D/counts/msgs-final"; rm -f "$D/counts/msgs-final"/c*
i=0; for c in $(git rev-list --reverse 6fde869..r6/pr-observer); do i=$((i+1)); git cat-file commit "$c" | sed '1,/^$/d' > "$D/counts/msgs-final/c$i"; cmp -s "$D/counts/msgs-final/c$i" "$D/msgs/c$i" || { echo "   c$i differs from msgs/c$i"; fail=1; }; done
$P -I "$D/tools/check_msg.py" "$D"/counts/msgs-final/c{1..11} || fail=1
echo "   subjects equal to r5: $(diff <(git log --format=%s 6fde869..r5/pr-observer) <(git log --format=%s 6fde869..r6/pr-observer) >/dev/null && echo yes || { fail=1; echo NO; })"
echo "   bodies changed: $(paste <(git rev-list --reverse 6fde869..r5/pr-observer) <(git rev-list --reverse 6fde869..r6/pr-observer) | nl -w1 -s' ' | while read -r i a b; do cmp -s <(git log -1 --format=%B $a) <(git log -1 --format=%B $b) || printf 'c%s ' $i; done)"
echo "   author/committer: $(git log --format='%an <%ae>|%cn <%ce>' 6fde869..r6/pr-observer | sort -u)"
echo "   '<earlier-model-name>' in messages $(git log --format=%B 6fde869..r6/pr-observer | grep -ci <earlier-model-name>), in tree $(git grep -il <earlier-model-name> r6/pr-observer | wc -l), in diff $(git diff 6fde869 r6/pr-observer | grep -ci <earlier-model-name>)"
echo "   'upstream' in messages $(git log --format=%B 6fde869..r6/pr-observer | grep -ci upstream), in the five docs $(git grep -i upstream r6/pr-observer -- $MD5 | wc -l)"
echo "   trailer lines $(git log --format=%B 6fde869..r6/pr-observer | grep -c '^Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>$') of $(git log --format=%B 6fde869..r6/pr-observer | grep -c 'Co-Authored-By')"
echo "   blank line before trailer: $(i=0; for f in "$D"/counts/msgs-final/c*; do tail -2 "$f" | head -1 | grep -q '^$' && i=$((i+1)); done; echo $i) of 11"
git diff --check r5/pr-observer r6/pr-observer && echo "   diff --check clean"
echo "== control-run and term checks in the five docs and the messages (r6/pr-observer)"
for pat in 'reference run' 'reference case' 'model-off' 'model off' 'no-request' 'run without requests' 'run with no request\b' 'POD fields' 'true positions' 'about 2 minutes' '15 to 27'; do
  n=$(git grep -n -i -P "$pat" r6/pr-observer -- $MD5 | wc -l); m=$(git log --format=%B 6fde869..r6/pr-observer | grep -c -i -P "$pat")
  echo "   '$pat': docs $n, messages $m"
done
git grep -n -i -P 'reference (run|case)' r6/pr-observer -- $MD5 | sed 's/^/      /'
echo "== links and quoted references at c6..c11"
i=0; for c in $(git rev-list --reverse 6fde869..r6/pr-observer); do i=$((i+1)); [ $i -lt 6 ] && continue
  $P -I "$D/tools/check_links.py" "$R" "$c" > "$D/counts/links_c$i.txt"; e=$?
  echo "c$i ${c:0:7} exit $e, ok $(grep -c '^ok' "$D/counts/links_c$i.txt"), broken $(grep -c BROKEN "$D/counts/links_c$i.txt")"; [ $e = 0 ] || fail=1
done
echo "== numbers kept (r5 doc -> r6 doc, as committed)"
num() { git show "$1" > "$D/counts/a.tmp"; git show "$2" > "$D/counts/b.tmp"; $P -I "$D/tools/numbers_kept.py" "$D/counts/a.tmp" "$D/counts/b.tmp" | sed "1s|^[^:]*:|$3:|; s/in r4/in r5/; s/in r5:/in r6:/; s/(r4, r5)/(r5, r6)/"; }
num r5/pr-observer:Solver_Examples/PODFoam/validation/README.md r6/pr-observer:Solver_Examples/PODFoam/validation/README.md validation/README.md
num r5/pr-fix:README.md r6/pr-fix:README.md README.md@fix
num r5/pr-observer:README.md r6/pr-observer:README.md README.md@observer
num r5/pr-observer:Solver_Examples/PODFoam/HOOKS.md r6/pr-observer:Solver_Examples/PODFoam/HOOKS.md HOOKS.md
num r5/pr-observer~2:Solver_Examples/PODFoam/llm_demo/README.md r6/pr-observer~2:Solver_Examples/PODFoam/llm_demo/README.md llm_demo/README.md@c9
num r5/pr-observer:Solver_Examples/PODFoam/llm_demo/README.md r6/pr-observer:Solver_Examples/PODFoam/llm_demo/README.md llm_demo/README.md@c10-11
num r5/pr-observer:Solver_Examples/PODFoam/llm_demo/hpc/README.md r6/pr-observer:Solver_Examples/PODFoam/llm_demo/hpc/README.md llm_demo/hpc/README.md
rm -f "$D/counts/a.tmp" "$D/counts/b.tmp"
echo "== passages the code cites are still there"
echo "   hpc/README.md names build_llama_cuda.sh: $(git show r6/pr-observer:Solver_Examples/PODFoam/llm_demo/hpc/README.md | grep -c build_llama_cuda.sh) lines"
echo "   HOOKS.md explains the left-out empty directions: $(git show r6/pr-observer:Solver_Examples/PODFoam/HOOKS.md | grep -c 'leaves out empty directions') line"
echo "== committed docs equal the r6docs files"
for pair in "r6/pr-observer:Solver_Examples/PODFoam/validation/README.md validation_README.md" "r6/pr-fix:Solver_Examples/PODFoam/validation/README.md validation_README.md" "r6/pr-observer:Solver_Examples/PODFoam/HOOKS.md HOOKS.md" "r6/pr-observer~2:Solver_Examples/PODFoam/llm_demo/README.md llm_README_c9.md" "r6/pr-observer:Solver_Examples/PODFoam/llm_demo/README.md llm_README_c10.md" "r6/pr-observer:Solver_Examples/PODFoam/llm_demo/hpc/README.md hpc_README.md" "r6/pr-fix:README.md README_fix.md" "r6/pr-observer:README.md README_obs.md"; do
  set -- $pair; cmp -s <(git show "$1") "$D/r6docs/$2" && echo "   $2 = $1" || { echo "   $2 DIFFERS from $1"; fail=1; }
done
echo "== worktrees"
for w in wt-fix wt-obs; do echo "   $w $(git -C "$D/$w" rev-parse --short HEAD) $(git -C "$D/$w" rev-parse --abbrev-ref HEAD), status lines $(git -C "$D/$w" status --short | wc -l)"; done
echo "OVERALL $([ $fail = 0 ] && echo PASS || echo FAIL)"
