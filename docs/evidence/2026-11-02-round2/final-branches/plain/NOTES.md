# DEAI-DOCS: r5/pr-fix and r5/pr-observer (2026-11-02)

Task: ROUND2_DECISIONS.md section F, scope 1. The five PR docs were rewritten as
plain technical prose without the AI tone. They are not simplified and have no
glossary. Facts and numbers stay. Each doc went into the commit that introduces or
changes it. The code trees are unchanged.

## Final heads

| Branch | Head | Worktree |
|---|---|---|
| r5/pr-fix | d4ebf5cfa2896a6aec6dee44b8b7ca70ff2f36ae | wt-fix (clean) |
| r5/pr-observer | ca68b32be74908c7443f64a47489a500abfc6748 | wt-obs (clean) |
| base | 6fde8698071b56f913c5e92c647f22ab38b26466 | |

r5/pr-fix equals r5/pr-observer~4.

## Commits r4 -> r5

| # | r4 | r5 | Tree | Message |
|---|---|---|---|---|
| 1 | 5b3e5a3 | 28540d8 | same | rewritten |
| 2 | d686a64 | 5e7fe8b | same | rewritten |
| 3 | aaf80a6 | 9337a0d | same | rewritten |
| 4 | d01af1a | 26b2a85 | same | rewritten |
| 5 | a7501b1 | dd63080 | same | rewritten |
| 6 | 8376b00 | 8207a2e | validation/README.md | rewritten |
| 7 | 8954b25 | d4ebf5c | + README.md | rewritten |
| 8 | 371adba | e556767 | + HOOKS.md | rewritten |
| 9 | e05643e | d0927ad | + llm_demo/README.md | rewritten |
| 10 | 6e41943 | e55ddad | + llm_demo/README.md, hpc/README.md | rewritten |
| 11 | 24e9df6 | ca68b32 | + README.md | rewritten |

The full hashes are in build_r5.out. The commits were made with `git commit-tree`
(tools/build_r5.sh) and keep the r4 author, e-mail and author date. The committer
is Seungmin Yome <wab8131028@gmail.com>. All 11 subjects equal the r4 subjects, so
the PR texts' commit lists stay valid. The first build is in build_r5.first.out.
Commits 10 and 11 were rebuilt once after a wording fix in hpc/README.md. That
first pair, 86d510b and c27489f, is on no branch.

## Proofs (verify_r5.out, tools/verify_r5.sh)

- `git diff <r4> <r5> -- ':!*.md'` is empty for all 11 pairs.
- Commits 1-5 have the same tree as r4.
- Every r5 commit changes the same files as its r4 commit.
- r5/pr-observer differs from r4/pr-observer only in the five docs.
- r5/pr-fix differs from r4/pr-fix only in README.md and validation/README.md.
- Messages: 11/11 within limits. Subjects are 26-67 chars and bodies 5-8 lines,
  12 for commit 1. Lines are at most 80 chars, with exactly one Opus trailer.
- "<earlier-model-name>" count: 0 in messages, tree and diff. "upstream": 0 in messages and docs.
- `git diff --check` is clean.
- Links: every relative link at commits 6-11 resolves, with 0 broken. No link
  inside the docs uses an anchor. The quoted section references "U and p on
  openfoam.com", "POD schedule at write steps" and "POD schedule" match a bold label.
  https://github.com/seungminyome/PythonFOAM returns HTTP 200. Three links of the
  original README were also tried: YouTube and openfoam.com return 200, and Docker
  Hub ends in a redirect loop. Its other four links were not tried.
- Numbers: every number and every identifier with a digit in each r4 doc is still in
  the r5 doc (tools/numbers_kept.py; 0 missing in all 7 file versions). The
  spelled-out number words were compared too. Two dropped quantifiers were restored:
  "all modes" and "once".

## Section-F counts per file (tools/style_counts.py)

Words exclude table pipes. The README rows count only the PR's own sentences
(tools/readme_pr_text.py).

| File | Words | Sentences > 35 words | Explanatory parentheses | Max numbers per paragraph | Banned words |
|---|---|---|---|---|---|
| validation/README.md | 1647 -> 1788 | 8 -> 0 | 20 -> 0 | 7 -> 2 | 0 -> 0 |
| HOOKS.md | 850 -> 878 | 3 -> 0 | 12 -> 0 | 1 -> 1 | 1 -> 0 |
| llm_demo/README.md at commit 9 | 1964 -> 2069 | 5 -> 0 | 16 -> 0 | 9 -> 2 | 1 -> 0 |
| llm_demo/README.md at commit 10 | 2002 -> 2107 | 5 -> 0 | 16 -> 0 | 9 -> 2 | 1 -> 0 |
| llm_demo/hpc/README.md | 931 -> 969 | 4 -> 0 | 7 -> 0 | 15 -> 2 | 0 -> 0 |
| README.md, PR text at commit 7 | 135 -> 138 | 1 -> 0 | 1 -> 0 | 1 -> 1 | 0 -> 0 |
| README.md, PR text at commit 11 | 183 -> 187 | 2 -> 0 | 2 -> 0 | 1 -> 1 | 0 -> 0 |

The banned words were "therefore" in HOOKS.md and "nearly" in llm_demo/README.md.
counts/style_counts.jsonl has the lists.

Commit messages, before -> after, as long sentences / parentheses / max numbers /
banned. c1 went from 2/3/3/0 to 0/0/2/0. c2, c8 and c11 went from 1/1 to 0/0. c3 went
from 1/1 to 0/1; the remaining count is `argList(..., initialise=false)`, which is
code. c6, c7 and c10 had one long sentence and now have none. c4, c5 and c9 had
no long sentence or parentheses but did have chains of three or more clauses, so
they were rewritten too.

H2 shares (tools/h2_shares.py, counted like readme_shares.py) stay within 2 points.
The largest change is llm_demo/README.md Limits: 20.9 -> 22.8 at commit 9 and
20.5 -> 22.4 at commit 10. The root README's shares move by 0.3 points or less.
validation/README.md renames "Pass criteria (`verify.py`)" to "What `verify.py`
checks", which moves from 9.5 to 10.9. counts/h2_shares.jsonl has all values.

## What changed in form

- Run-on sentences were split, and parentheses became sentences, list items or
  tables.
- New tables: the `fixed-pimple` settings and the passing-run values in
  validation/README.md. In llm_demo/README.md, the E2B disk and time table and,
  under Limits, the picture tests, the suite runs and the OpenFOAM 8 differences.
  In hpc/README.md, the job settings and the tested runs.
- New H3 headings: "Picture tests", "Versions and runs" and "Why OpenFOAM 8
  differs" in llm_demo/README.md, and "Tested runs" in hpc/README.md.
- "What changes in PODFoam" is kept, so the anchor `#what-changes-in-podfoam` that
  the staged fork docs need stays valid. Nothing in the staged docs or texts links
  to the renamed "Pass criteria" heading.
- First-use explanations for terms outside CFD: vision-language model, llama-server
  and Gemma 4 / E2B.
- One judgement word was replaced by a number. "The four slices are nearly the same
  flow" became "the true positions agree to 0.1 % between the four slices". The
  source is r3/docs/stage/docs/results-20261102.md lines 326-327, the slice run of
  job 25080032.
- One history phrase was restated as a result. "The prebuilt server as the earlier
  script left it ... (the dropped soname links, fixed above)" became a table row: a
  server without its soname links stops with that message, and setup_12b.sh keeps
  the links.
- In verify_async.py's description, "baseline" became "no-request case", so that
  "constant baseline" keeps one meaning.
- Facts checked in code while rewriting:
  - LLM_MAX_TOKENS takes values from 32 up to the default (llm_client.py lines
    176-181).
  - LLM_CALLBACK_DEADLINE_S wins over LLM_TIMEOUT_S (python_module.py line 1236).
  - validation/python_module.py refuses every rank but 0.
  - async_v2.slurm sets the defaults in hpc/README.md (lines 44-52).

## Jobs

None. Only the docs changed, and every code tree equals the r4 trees, so the r4
verification carries over.

## Not done

- No build, validation or test run on the r5 hashes, because the code trees are
  unchanged.
- No KO translation of the rewritten docs. That belongs to the fork/KO task, which
  must translate from these r5 files and use the new headings.
- Fork main integration, fork docs, PR bodies and e-mails (section F scopes 2 and 3)
  were not done here. Those tasks should take the r5 heads.
- No second reader. The counts come from scripts, and the fact check was one
  sentence-by-sentence read against r4.
- The sentence counter splits only at . ! ? followed by a space. Clause chains are
  judged by reading, and "2+ semicolons" is the only scripted sign of them.
- Nothing pushed, no PR, no e-mail. No existing branch or worktree was changed. main
  6677bac, PythonFOAM-pr bf7a06e and PythonFOAM-Korean 5c56995 are clean. r4/fix/wt
  and r4/fix/wt-obs are clean. No Slurm job was submitted or touched.

## Files

- r4docs/: the r4 docs as extracted (README_base.md = 6fde869).
- r5docs/: the rewritten docs, byte-equal to the committed blobs.
- msgs/c1-c11: the commit messages.
- tools/: style_counts.py, h2_shares.py, readme_pr_text.py, numbers_kept.py,
  check_links.py, build_r5.sh and verify_r5.sh.
- counts/: per-file counts, link reports links_c6-c11.txt, the final messages and
  their bodies.
