# PR-DOCS: r6/pr-fix and r6/pr-observer (2026-11-02)

Task: ROUND2_DECISIONS.md section G4, with the PR-branch items of R4_DIGEST.md
(REVIEW 0 must_fix 1-3 and should_fix 1-5, REVIEW 1 must_fix 7 and its should_fix
items on PR-branch files), G2 times and the G3 term. Docs, commit metadata and
records only. Code trees are unchanged.

## Final heads

| Branch | Head | Worktree |
|---|---|---|
| r6/pr-fix | 6df2fa26d1f5498e6262d3cc531037d817272b0d | wt-fix (clean) |
| r6/pr-observer | 441417937a9464fe086263999f35696c828ceb51 | wt-obs (clean) |
| base | 6fde8698071b56f913c5e92c647f22ab38b26466 | |

r6/pr-fix equals r6/pr-observer~4. Both branches are local only, in
$G/PythonFOAM. Nothing was pushed.

## Commits r5 -> r6

| # | r5 | r6 | Tree vs r5 | Message vs r5 | Author date (-0700) |
|---|---|---|---|---|---|
| 1 | 28540d8 | 17dc16a | same | same | 14:30:55 |
| 2 | 5e7fe8b | 9c577ba | same | same | 14:31:05 |
| 3 | 9337a0d | a8e4df7 | same | same | 14:32:03 |
| 4 | 26b2a85 | 50a22fb | same | body: "POD fields" -> "mode files" | 14:32:17 |
| 5 | dd63080 | a172215 | same | same | 14:32:23 |
| 6 | 8207a2e | 7f04a4e | validation/README.md | same | 14:33:52 |
| 7 | d4ebf5c | 6df2fa2 | validation/README.md | same | 14:34:33 |
| 8 | e556767 | c066e65 | + HOOKS.md | same | 14:35:45 |
| 9 | d0927ad | 9b776db | + llm_demo/README.md | body: control-run term | 14:51:08 |
| 10 | e55ddad | bb1cb4b | + llm_demo/README.md | same | 14:51:17 (was 14:37:53) |
| 11 | ca68b32 | 4414179 | + llm_demo/README.md | same | 14:51:18 (was 14:38:03) |

Full hashes: build_r6.out. Built with tools/build_r6.sh 1793669421 (build_r6.base);
the same argument gives the same hashes. Each doc change sits in the commit that
introduces or changes the doc: validation/README.md in 6, HOOKS.md in 8,
llm_demo/README.md in 9 and 10. hpc/README.md and the root README are unchanged.

Dates. Author name, e-mail and date are r5's, except commits 10 and 11. Their r5
author dates (14:37:53, 14:38:03) were earlier than commit 9's 14:51:08. r4 had
re-created 6e41943 and 24e9df6 on top of e05643e at 14:51:17 (their committer
date), so commits 10 and 11 now carry 14:51:17 and 14:51:18. Committer dates are
2026-11-02 18:30:22 to 18:30:32, one second apart. Commits 1-5 needed new hashes
because their r5 committer dates were not strictly increasing (c1 and c2 both
16:38:48, c3-c6 all 16:38:49).

The first build attempt stopped at commit 6 (argument order in set_file). It left
five commits on no branch: dc6b0d4, 66f7bbd, 9aacc13, 33da855, c70e46c.

Fill for TODO-HASH, in order: 17dc16a 9c577ba a8e4df7 50a22fb a172215 7f04a4e
6df2fa2 (fix), then c066e65 9b776db bb1cb4b 4414179 (observer). Subjects equal
r5's, 11 of 11, so the commit lists in the texts stay valid.

## Fixes applied

| Item | File, commits | Change | Source |
|---|---|---|---|
| R0 must_fix 1 | validation/README.md, c6+ | "Checked calls": each check stops with its own message; only the wrong-shape message names the shape; the `online_mode = False` runs stopped with `Non-finite SVD result` | PythonComm.H lines 99, 110, 117-123, 154 at r6/pr-observer; r4/fix/scenarios/scen-{8,v2012,v2106,v2212}/scenarios.json, wi3 and wi6 tails |
| R0 must_fix 2 | llm_demo/README.md, c9 and c10 | "Versions and runs": build and bridge validation on the four versions; the observer with no model on all four in 2D and 3D, serial and on 2 ranks | r4 text 24e9df6 llm_demo/README.md lines 217-218; validation/README.md line 3; validation/python_module.py rank check |
| R0 must_fix 3 = R1 must_fix 7, G2 | llm_demo/README.md, c9 and c10 | E2B table: "15 to 28 minutes", "2 to 4 minutes" | G2; r4/observer/NOTES.md finding 1 (103-223 s, 912-1669 s; job 25090644 223 s and 1669 s) |
| R0 should_fix 1 | HOOKS.md, c8+ | "POD schedule": the windows differ only at `podSvdInterval` 0; above 0 the schedule is the same with or without `analysis_func` | PythonComm.H lines 24-25 and 75-77 |
| R0 should_fix 2, R1 should_fix 1, G3 | llm_demo/README.md c9, c10; message c9 | "model off" / "model-off case" / "no-request case" -> list item "no model requests", first mention "the same run with no model requests", later "the run with no model requests"; c9 body "the run with no request" -> "the same run with no model requests" | G3 |
| R0 should_fix 3 | commits 10, 11 | author dates after commit 9 | see Dates |
| R0 should_fix 4 | records | exact H2 shares below; file record of the E5 user-site numpy check in usersite-test/usersite-check.txt | this folder |
| R0 should_fix 5a | validation/README.md | 107-character line rewrapped | |
| R0 should_fix 5b, R1 should_fix 2 | llm_demo/README.md | slice caveat moved after the "Picture tests" table; "true positions" -> "the answer-key positions of the fastest flow and lowest pressure" | r2/slice-3d/NOTES.md "the four slices give the same true positions to 0.1 % at every step" |
| R0 should_fix 5c | llm_demo/README.md | "Picture tests" column header "Gemma 4 model", so 12B is named as a Gemma 4 model at its first mention in c9 | |
| R0 should_fix 5e | validation/README.md; message c4 | "POD fields" -> "mode files" (the term of the "Mode files" bullet) | |
| R1 should_fix 13 (llm_demo part) | llm_demo/README.md | OpenFOAM 8 table: differences in m/s and m²/s², plus a row "v2212: peak speed and range of p, 37.2 and 379" | r2/of8-cause/compare-final.json: v2212/2d/A U_peak 37.210, p_range 378.92; of8_vs_v2212_same_variant 2d/A U_max 3.1104, p_max 23.235 |

## Skipped, with reasons

- R0 should_fix 5d (unused `#include <chrono>` in PODFoam.C on r6/pr-fix): code
  change; code is final this round.
- R0 should_fix 4, first part: r4/plain/NOTES.md was not edited (another stage's
  record). The exact values are here instead.
- R1 should_fix 3-12 and the non-llm_demo parts of 13: they concern fork main, KO
  docs or index.html, not PR-branch files.
- R2 items: texts, not PR-branch files.

## Proofs (verify_r6.out, tools/verify_r6.sh): OVERALL PASS

- `git diff <r5> <r6> -- ':!*.md'` is empty for all 11 pairs (counts/pairs.txt).
- Commits 1-5: same tree objects as r5. Every r6 commit changes the same file list
  as its r5 commit.
- r5/pr-fix vs r6/pr-fix: only validation/README.md. r5/pr-observer vs
  r6/pr-observer: only HOOKS.md, llm_demo/README.md, validation/README.md.
- Author dates and committer dates strictly increase along the 11 commits; each
  committer date is later than its author date. Author and committer are Seungmin
  Yome <wab8131028@gmail.com> on all 11.
- Messages: tools/check_msg.py 11/11 OK (subjects 26-67 chars, bodies 5-8 lines,
  12 for c1, lines at most 80 chars). Exactly one trailer
  "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" after a blank line, 11
  of 11. Bodies changed: c4, c9. The committed messages equal msgs/c1-c11.
- The banned name: 0 in messages, tree and diff. "upstream": 0 in messages and
  the five docs. `git diff --check` clean.
- Terms in the five docs and the messages: "model-off", "model off",
  "no-request", "run without requests", "run with no request", "POD fields",
  "true positions", "about 2 minutes", "15 to 27" all 0. "reference case" 1
  (llm_demo Settings, POD_REFERENCE_RUN) and "reference run" 3 (hpc/README.md
  lines 27, 32, 69, all POD_REFERENCE_RUN).
- Links (tools/check_links.py at c6-c11): 4, 5, 7, 8, 10, 12 ok, 0 broken. No link
  inside the docs uses an anchor. The quoted references "U and p on openfoam.com",
  "POD schedule at write steps" and "POD schedule" match labels. Headings of all
  seven doc versions are unchanged (counts/headings.txt), so anchors used from
  outside, such as #what-changes-in-podfoam, still resolve.
  https://github.com/seungminyome/PythonFOAM returned HTTP 200 (counts/external_links.txt).
- Numbers (tools/numbers_kept.py, r5 doc -> r6 doc as committed): 0 numbers and 0
  identifiers missing in all 7 doc versions. New number: 28. One of the two "27"
  is gone.
- Code-cited passages kept: hpc/README.md names build_llama_cuda.sh (5 lines);
  HOOKS.md keeps "leaves out empty directions".

## Numbers or qualifiers a fix removed

- llm_demo/README.md, c9 and c10: "15 to 27 minutes" -> "15 to 28 minutes" (G2).
- llm_demo/README.md, c9 and c10: "about 2 minutes" -> "2 to 4 minutes" (G2).
- No other number of the r5 docs was removed.

## Section-F counts per changed file, r5 -> r6 (tools/style_counts.py)

| File | Words | Sentences > 35 words | Explanatory parentheses | Max numbers per paragraph | Banned words |
|---|---|---|---|---|---|
| validation/README.md (c6-c11) | 1788 -> 1797 | 0 -> 0 | 0 -> 0 | 2 -> 2 | 0 -> 0 |
| HOOKS.md (c8-c11) | 878 -> 893 | 0 -> 0 | 0 -> 0 | 1 -> 2 | 0 -> 0 |
| llm_demo/README.md at c9 | 2069 -> 2102 | 0 -> 0 | 0 -> 0 | 2 -> 2 | 0 -> 0 |
| llm_demo/README.md at c10-c11 | 2107 -> 2140 | 0 -> 0 | 0 -> 0 | 2 -> 2 | 0 -> 0 |
| message c4 body | 82 -> 82 | 0 -> 0 | 0 -> 0 | 2 -> 2 | 0 -> 0 |
| message c9 body | 103 -> 105 | 0 -> 0 | 0 -> 0 | 0 -> 0 | 0 -> 0 |

Unchanged files: hpc/README.md (969 words, all counts 0 or at most 2 numbers),
root README PR text at c7 (138 words) and c11 (187 words), all counts 0 or 1.
No sentence has two or more semicolons. HOOKS.md's 2 numbers are the two "0" of
`podSvdInterval` in the "POD schedule" paragraph. counts/style_counts.jsonl has
the lists.

## H2 shares (tools/h2_shares_exact.py, counted like h2_shares.py)

r5 -> r6 (counts/h2_r5_r6.txt): largest change per file validation/README.md
+0.256 ("What changes in PODFoam" 46.429 -> 46.684), HOOKS.md +0.910
(Behaviour 40.833 -> 41.744), llm_demo/README.md Limits +0.648 at c9
(22.771 -> 23.419) and +0.643 at c10 (22.384 -> 23.027).

r4 -> r5, exact (counts/h2_r4_r5.txt), the values REVIEW 0 should_fix 4 asked for:
validation/README.md "What changes in PODFoam" 48.374 -> 46.429 (-1.945); the renamed
section "Pass criteria (`verify.py`)" 9.462 -> "What `verify.py` checks" 10.928
(+1.466); hpc/README.md Commands 23.883 -> 25.818 (+1.934); llm_demo/README.md
Limits 20.852 -> 22.771 (+1.919) at c9 and 20.468 -> 22.384 (+1.916) at c10;
HOOKS.md largest +1.334 (Behaviour). r4/plain/NOTES.md named only the Limits change
and called it the largest; the validation and hpc changes are larger.

r4 -> r6 (counts/h2_r4_r6.txt): llm_demo/README.md Limits 20.852 -> 23.419 (+2.567)
at c9 and 20.468 -> 23.027 (+2.559) at c10. Against r4 this is more than 2 points.
Against r5, the docs on the branches before this round, it is +0.65. The growth is
the restored slice caveat, the split "Versions and runs" sentence and the third row
of the OpenFOAM 8 table. All other sections stay within 2 points of r4.

## E5 record (usersite-test/usersite-check.txt)

Login node mblog1, 2026-11-02 18:32, run.sh of r6/pr-fix (blob 13a9370, the same
as at r4 8954b25). /usr/bin/python3 3.9.25 has no numpy. A stand-in package named
numpy in a PYTHONUSERBASE user site imports without PYTHONNOUSERSITE. With that user
site, PYTHON=/usr/bin/python3 and POD_WORKSPACE in this folder, run.sh printed "Set
PYTHON to a Python with numpy (now: '/usr/bin/python3')", exited 1 and made no
workspace. The stand-in is not a real numpy; the check only imports the name.

## Observation

POD_REFERENCE_RUN is called "reference case" in the llm_demo Settings table and
"reference run" in hpc/README.md. The task kept "reference case" for it, so both
stay. Neither names the run with no model requests.

## Jobs

None. No Slurm job was submitted, queried or touched.

## Not done

- No build, validation or test on the r6 hashes: every code tree equals r5's, which
  equal r4's verified trees (8954b25 and 24e9df6).
- No KO translation, fork main (r6/main, r6/ko-main), texts, PR bodies or e-mails.
- r4/plain/NOTES.md and the other round-4 records were not edited.
- No second reader; the counts come from the scripts and the facts from one read
  against the named sources.
- The sentence counter splits only at . ! ? followed by a space; clause chains were
  judged by reading.
- Nothing pushed, no PR, no e-mail, nothing at argonne-lcf. No existing branch or
  worktree changed: main 6677bac, r5/pr-fix d4ebf5c, r5/pr-observer ca68b32,
  PythonFOAM-pr bf7a06e and PythonFOAM-Korean 5c56995 are clean.

## Files

- r5docs/: the r5 docs as committed (README_base.md = 6fde869). r6docs/: the r6
  docs, byte-equal to the committed blobs.
- msgs-r5/, msgs/: the r5 and r6 commit messages, byte-exact.
- tools/: build_r6.sh, verify_r6.sh, h2_shares_exact.py, and copies of
  style_counts.py, h2_shares.py, numbers_kept.py, check_links.py,
  readme_pr_text.py (r4/plain/tools) and check_msg.py (r4/fix).
- counts/: pairs, links per commit, final messages, H2 shares, style counts,
  diffs of the llm_demo README versions.
- build_r6.out, build_r6.base, verify_r6.out, usersite-test/.
