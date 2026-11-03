# Task FIX (phase 4) — r4/pr-fix and r4/pr-observer, 2026-11-02 (Claude Opus 5.5)

G=/cluster/medbow/gscratch/syome/github_repos, W=$G/pod-versions-20261030, F=$W/r4/fix (this folder).
Inputs read: $W/auto/ROUND2_DECISIONS.md (A-E; E wins), $W/auto/R3P2_DIGEST.md, and the full REVIEW 0/1 texts from the
workflow journal (copied to F/ref/reviews_full.txt and F/ref/reviews_all.txt, since the digest truncates them).
Nothing pushed, no PR, no e-mail. No existing branch, worktree or repository was changed (checks at the end).

## Heads

| Branch | Tip | Tree | Worktree |
|---|---|---|---|
| r4/pr-fix | 8954b2544d0f669d0079f6138eec6983944cf4d5 | e2dd9e28c00b | F/wt (clean) |
| r4/pr-observer | 24e9df6f5640594e2dbbd9a817231717fe8310ef | 251f9654cc5b | F/wt-obs (clean) |
| base | 6fde8698071b56f913c5e92c647f22ab38b26466 | | |

r4/pr-observer = r4/pr-fix (all 7 commits, README included) + 4 commits, so the observer branch is a descendant of the
fix branch (r3/pr-observer had left out the fix README commit; decision A says "pr/podfoam-fix + ...").
diff 6fde869..r4/pr-fix: 15 files +951/-166; 6fde869..r4/pr-observer: 47 files +9068/-166 (one llm_demo README
sentence more than the stat taken at 7ef9588).

| # | Commit | Subject | Built from |
|---|---|---|---|
| 1 | 5b3e5a32188c399e850c3e177547efcd85c04c75 | PODFoam: NumPy owns each snapshot; calls into Python are checked | dec3da1 + E2, E3, E6 |
| 2 | d686a64dbec54a7cf82dc3852c406775a9144adc | PODFoam_Debug, APMOSFoam, AEFoam: NumPy owns each snapshot too | 9899952 + E6 |
| 3 | aaf80a66fd6c9eeac7d309f8d513f8685f4d0275 | PODFoam: setRootCaseLists.H; floating-point traps off around Python | 5c76dcc (message unchanged) |
| 4 | d01af1ab303d7b01fd5d134e5dc34601e7f75ad7 | PODFoam: optional podSvdInterval in controlDict | 8c28c51, schedule wording |
| 5 | a7501b1ff420aed940995ba5db579b5d51264b52 | pEqn: on openfoam.com select pFinal only on the final corrector | e3d5da5 pEqn.H only (moved before validation) |
| 6 | 8376b00d9706b6b0f5a1e959ac7c8ef82800f74e | PODFoam: bridge validation | ce3639b + e3d5da5's README passages + E3/E4/E5 |
| 7 | 8954b2544d0f669d0079f6138eec6983944cf4d5 | README: PODFoam snapshot fix and validation | cbd0e89 + E4/E6 |
| 8 | 371adbab9c8b006069a92c9501431a187c4cc207 | PODFoam: optional analysis_func and mesh_func hooks | 0bf7161 + E7 |
| 9 | e05643e3dbec0c3f70eddcf22a8b885e97faf4e3 | PODFoam llm_demo: an observer asking a local vision-language model | 29a5e30 + E7/E8 (message unchanged) |
| 10 | 6e41943cffab1008480546e0b5c8d7195dceefe4 | PODFoam llm_demo/hpc: the GPU path | 54c117b (hpc/ identical; message unchanged) |
| 11 | 24e9df6f5640594e2dbbd9a817231717fe8310ef | README: PODFoam hooks and the observer example | 276ea8e's added line, reworded (E7) |

Author and committer of all 11: Seungmin Yome <wab8131028@gmail.com>. Message checks (F/check_msg.py and a git log
pass): subjects 26-67 chars; bodies 5-8 lines (commit 1: 12); longest body line 80; each ends with a blank line and
exactly "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; `git log --format=%B 6fde869..r4/pr-observer`
has 0 matches of the banned trailer name and 0 "upstream" (case-insensitive). The banned name: 0 in the diff 6fde869..r4/pr-observer and 0 files in the
tip tree. "upstream", "current code", "current PODFoam", "original schedule", "observe only", "change nothing": 0 in
the added lines. Root .gitignore unchanged. Added lines matching /cluster, /gscratch, syome, medbow, uwyo, mblog,
argonne-lcf, hf_ tokens, ghp_, github_pat, wab8131028: 0.

Superseded commits, on no branch (reflog only; do not use): 987d1c7, 31ac13a, 7ef9588 (first llm_demo/hpc/README
commits; 7ef9588 = 24e9df6 minus one llm_demo/README.md sentence, and was the tree of the scenario, slice and first
smoke/Docker/validation runs below), and 9abefed, ccac791 (cherry-picks made without the -c identity flags: their
committer e-mail was the login host's; reset away within a minute, never exported or tested).

## What changed against r3, item by item

Section E:
1. Order 1 owned snapshots, 2 siblings, 3 setRootCaseLists/FPE, 4 podSvdInterval, 5 pEqn, 6 validation, 7 README.
   Validation now passes at its own commit on all four versions (below). No text claims a commit can be dropped alone
   (the pEqn message no longer refers to the validation).
2. Commit 1 body (12 lines) lists: mode files dimensionless zeroGradient; podTruncation (default 5) caps the modes
   written, more columns give one warning; case folder first on sys.path; Py_FinalizeEx at exit waits for non-daemon
   threads; a changed cell count stops the run; a write step with no snapshot since the last SVD collects one (the
   earlier code ran svd_func at every write step).
3. PythonComm.H: more than podTruncation columns -> the first podTruncation are written and
   "svd_func returned N modes; the first T (podTruncation) are written" is printed once per run (flag
   podTruncationWarned, max over ranks, so all ranks agree); 0 columns, wrong ndim/rows, wrong dtype/byte order and
   non-finite values in the written columns still stop. The finite check and the copy use the array's real column
   stride. Shape message now "Expected SVD shape (61620, 1 or more modes), got (...)". Scenario expectation updated
   (returns-six-modes, below); validation README and HOOKS.md say so.
4. In-repo docs: heading "What changes in PODFoam"; "PODFoam before this change" everywhere the old solver is meant;
   modes-equal statement limited to OpenFOAM 8 with a pointer to "U and p on openfoam.com"; new bullet "POD schedule at
   write steps" says the write-step rule is new (the earlier code ran svd_func at every write step; the shipped case
   writes every 100 steps, so its schedule is the same); PythonComm.H comments no longer say "original schedule".
   README: the siblings built on all four versions (jobs below), so the README says "`PODFoam`, `PODFoam_Debug`,
   `APMOSFoam` and `AEFoam` build on v2012, v2106, v2212 and 8" as a sentence under the list; the repository-wide
   "should compile" list is unchanged (no widening for the other examples, which were not built).
5. run.sh: PYTHONNOUSERSITE=1 exported and PYTHONHOME/PYTHONPATH unset before the numpy check; `fail()` prints
   "<step> failed; see <log>" for wmake, blockMesh, pimpleFoam and PODFoam; the --resume message was already there.
6. PythonCreate.H: PyUnicode_DecodeFSDefault for case paths. Sibling PythonComm.H: NULL check after PyArray_SimpleNew
   (PyErr_Print + FatalError "Cannot allocate the snapshot array"). Commit 2 message: "the first two snapshot columns,
   rows for AEFoam, come out equal". "Python 3 numpy wording": no review text with that title was found in the digest
   or the journal; I read it as the root README requirement line, now "The solvers themselves need only Python 3 with
   numpy, and the headers of both", and the validation README says PYTHON must be a Python 3 whose own site-packages
   hold numpy.
7. Hooks: root README line, hooks commit body, HOOKS.md, the PythonAnalysis.H header comment and the llm_demo README say
   the hooks change neither U nor p and that with analysis_func the POD step collects a snapshot at every step. HOOKS.md
   now has tables of the mesh_func arguments (dtype/shape/meaning, poly_cells as global indices in rank order) and the
   state keys (p_cells (cells,), u_cells (cells,3)), the slice_plane keys (normal, z_m, requested_z_m, z_source,
   moved_off_mesh_points, mesh_z_range_m; on failure z_m None plus error), the per-step gather cost, step = OpenFOAM time
   index, and "without analysis_func" in the schedule paragraph. PythonAnalysis.H comment at the call corrected (p_cells
   and u_cells may be left out). mesh_func lookup errors other than AttributeError are printed. python_module.py:
   _residual_summary reads residuals with .get (absent Ux/Uy/p left out); the snapshot_count check moved from
   _render_image into _summarize (so numbers-only observe mode is covered); two new unit tests
   (test_restart_window_is_checked_against_snapshot_count: step 105, snapshot_count 5, window 5;
   test_snapshot_count_mismatch_is_an_error: "snapshot window 5 != snapshot_count 6"); the telemetry test passes
   snapshot_count=5 for its five-snapshot window; module docstring and README Settings call LLM_ANALYSIS_STEP,
   LLM_SEQUENCE_STEPS and LLM_FINAL_STEP time indices. Unit-test count in the README 83 -> 85.
8. llm_demo/README.md Limits rewritten: OF8 cause = relaxationFactors reading (p 0.9, U 0.9 with one outer corrector;
   openfoam.com looks only for pFinal/UFinal; without the block within 0.0001 m/s and 0.0005 m²/s²); 12B suites 1000
   steps on v2012, v2212 and 8 plus the 6000-step default on v2212; 2-rank 12B request from rank 0 only on v2212 and 8;
   72 slice pictures read offline, 60/72 and 71/72 against 27 and 29, slices nearly one flow. Async suite "15 to 27"
   minutes on 8 CPUs (job 25089658: 1574 s = 26.2 min). Numbers from $W/r3/docs/stage/docs/results-20261102.md lines
   18-21, 166-171, 229-272, 305-332 and the existing README.

REVIEW 0 should_fix not overruled by E, also applied: nit (4) "a module with snapshot_func and svd_func" removed (the
schedule paragraph was rewritten). Items 7, 8, 10, 11 (PR body, Docker how-to, text hashes, copyright) are texts or the
user's decision, not branch content; copyright lines unchanged. REVIEW 1 should_fix 0-2, 4-8 applied as in E7/E8;
item 3 (PR draft citations) is a text; item 7 (3D slice never run on the new C++) is answered by the slice runs below.

## Verification (all jobs --account=me5475; CPU partitions teton,non-investor,wildiris,mb, --exclude=t527)

Exports of every commit: F/src/<c1..c7,hooks,llm,hpc,obs>/ (HEAD file inside; F/src/obs-7ef9588 etc. keep the
superseded exports). Images: of-v2012-dev.sif, of-v2106-dev.sif, of2212.sif, of-8.sif; Docker = upstream-docker.sif
($W/pr/maint-review/images). Python /gscratch/syome/conda/s4f (3.11.16, numpy 2.4.6).

Builds (F/builds/<ver>-<n>-<job>/log.build; F/logs/bv-*.out):
- jobs 25090326 v2012, 25090327 v2106, 25090328 v2212, 25090329 8: c1-c7, hooks, llm (987d1c7), hpc (31ac13a),
  obs (7ef9588) = 44/44 exit 0, 0 lines matching "warning" in each log.
- jobs 25090475 v2012, 25090476 v2106, 25090477 v2212, 25090478 8: llm e05643e, hpc 6e41943, obs 24e9df6 = 12/12
  exit 0, 0 warnings. Every commit of both final branches is built on all four versions.
validation/run.sh (F/runs/<ver>-<n>/pod-*/verification.json), PASS = 20/20:
- c6 8376b00, c7 8954b25, hooks 371adba, obs 7ef9588 (jobs 25090326-29) and obs 24e9df6 (jobs 25090475-78) on
  v2012, v2106, v2212: max_Co 0.211076243341, max snapshot error 5.00009e-11, max mode error 4.94174e-13, 45 field
  files, U/p agreement with pimpleFoam true; on 8: max_Co 0.21212590429, 5.00009e-11, 4.98546e-13, 45 files. Same
  numbers as phase 3 (r3/assemble NOTES). Default runs stage fixed-pimple and fixed-pod only.
- `--baseline --resume` on each obs run: exit 0, PASS, stages baseline-pimple; its pimpleFoam exit 0 on 8 and 1 on
  v2012/v2106/v2212 (the shipped case's divergence, recorded only), 8/8 runs.
- export check: 0 files newer than HEAD outside validation/runs in src/obs after the runs.
Docker image (Ubuntu 18.04.5 LTS, g++ 7.5.0, Python 3.6.9; inner script r3/solver/jobs/docker_inner.sh unchanged):
- job 25090330: c7 8954b25 run.sh PASS and run.sh --baseline PASS; obs 7ef9588 PASS and PASS.
- job 25090479: obs 24e9df6 run.sh PASS and --baseline PASS. 6/6; max_Co 0.21212590429, 5.00009e-11, 4.98546e-13.
run.sh failure paths (E5):
- login node, c7 run.sh with PYTHON=/usr/bin/python3 (3.9.25, no numpy) and a numpy only in a PYTHONUSERBASE user site
  (which `python3 -c 'import numpy'` imports without PYTHONNOUSERSITE): "Set PYTHON to a Python with numpy
  (now: '/usr/bin/python3')", exit 1, no run directory made.
- job 25090471 (v2106, copies of c7 with one deliberate break each): wmake (#error) exit 1 "wmake failed; see
  .../log.build"; blockMesh (broken blockMeshDict) exit 1 "blockMesh failed; see .../fixed-pimple/log.blockMesh";
  pimpleFoam (broken 0/p) exit 1 "pimpleFoam failed; see .../fixed-pimple/log.pimpleFoam"; PODFoam (svd_func raises)
  exit 1 "PODFoam failed; see .../fixed-pod/log.PODFoam"; each named log exists. 4/4.
pod_account at the fix tip 8954b25 (F/jobs/pod_account.sbatch = phase-3 script with my paths; inner/compare scripts
$W/matrix unchanged; F/account-runs/*/account.json; summary by r3/solver/jobs/summarize_account.py):
- shipped, 8 (25090315): U, p, phi byte-identical 2/2; mode files equal to the base's 0/30, with the overwrite
  reproduced 30/30; snapshot matrices: base col0==col1 6/6, fork 0/6, columns 1.. identical 6/6.
- stabilised, 8 (25090316): 10/10 byte-identical; 0/150 and 150/150; matrices 30/30, 0/30, 30/30.
- stabilised, v2012 (25090317), v2106 (25090318), v2212 (25090319): U, p, phi differ at 10/10 (max |dU| 0.05075,
  |dp| 846.8); modes 0/150 and 0/150 with the overwrite; fork-plainp (plain pEqn.solve()) 150/150 and U, p, phi
  byte-identical 10/10; matrices base 30/30, fork 0/30, columns 1.. 0/30.
- Identical in every count to phase 3 (jobs 25089069-73).
Siblings at commit 2 d686a64 (F/siblings/<ver>-<job>; jobs 25090304 v2012, 25090305 v2106, 25090306 v2212,
25090307 8): PODFoam_Debug, APMOSFoam, AEFoam 12/12 built, 0 warnings. Sizes (bytes): v2012 897984/893336/893024,
v2106 794768/794912/794616 (= phase 3 job 25089080), v2212 776064/780288/775896, 8 910728/905808/905592 (= phase 3
job 25089079). Recording run on 8 (25090307, r2/siblings round2 inner2.sh "recording" stage on the commit-2 build,
shipped case endTime 1.5e-4): exit 0, 222 steps, 2 snapshot files, 6 matrices, first two columns equal 0/6, and 6/6
matrices equal to the r2 Python-copy run (job 25088384 case-copy); F/siblings/8-25090307/record/record-check.json.
Scenarios + schedule + extra at the observer tip (tree 7ef9588 = 24e9df6 except llm_demo/README.md; drivers copied to
F/scenarios with paths changed; jobs 25090332 v2012 (requeued by Slurm 3 times, "user env retrieval failed", released
once by me), 25090333 v2106, 25090334 v2212, 25090335 8; compare F/scenarios/compare_r4.py -> compare_r4.json/.txt,
against phase-3 records r3/solver/scenarios/{scen,sched,scenx}-<ver> of jobs 25089075-78):
- scenarios: 46 names, 58 rows (57 on 8) per version as in phase 3, no driver errors; 231 of 236 version-rows equal.
  Changed, 5: returns-six-modes (fork) on v2012, v2106, v2212, 8: phase 3 exit 1 FOAM FATAL "Expected SVD shape (61620,
  1 to 5 modes), got (61620, 6)" -> now exit 0, End, finalized, 1 warning "svd_func returned 6 modes; the first 5
  (podTruncation) are written", 15 POD files (upod_0..4, vpod_0..4, wpod_0..4) whose values equal the first 5 returned
  columns (values_match true) — the E3 change; expectation updated in F/scenarios/scenarios.py (six-modes added to the
  value check). rankmodes-variance-rule (fork) v2106: the two "VARIANCE rank" lines in the other order (rank 1 first);
  exit, FATAL and content equal — two ranks print unordered.
- schedule: 26 rows per version; 103 of 104 equal; changed, 1: v2106 fork-par2 base-module plain wi3 svd0 had
  "step 4: 0 snapshots in C++ log, expected 1" in phase 3 (the log line joined to rank 1's unterminated print) and has
  0 problems now; 0 problems on all four versions.
- extra: 11 names, 15 rows per version, 60 of 60 equal.
- Rows that differ between versions are those of phase 3: the OpenFOAM 8 trap rows (traps-diverging-*,
  traps2-divergence-after-python, traps2-huge-initial-U, late-overflow-after-python, traps-env-unset), the base
  build's method-of-snapshots NaN count (9 vs 5 on 8) and the VARIANCE print order.
- New messages seen in the fork logs (4 versions each): "Expected SVD shape (61620, 1 or more modes), got (61617, 2)",
  "... got (61620)", "... got (61620, 0)", "svd_func returned 6 modes; the first 5 (podTruncation) are written",
  "podSvdInterval must be 0 or positive, not -1", "Ignoring non-callable analysis_func", and 24 lines of
  "analysis_func raised; this step's call ignored".
Hooks smoke (phase-3 inner script, hooks_tail.py and one-patch case of r3/solver/smoke, read only; F/smoke/<ver>-<job>):
- 7ef9588: 25090337 v2106, 25090338 8; 24e9df6: 25090481 v2106, 25090482 8 — identical results:
  A (Run_Case + validation module + hooks, podSvdInterval 3): 8 exit 0, 152 steps, 152 snapshots, 50 SVDs, 152
  analysis calls, End, finalized, mesh_func once with 7 args (centres (20540,3), volumes (20540,), (1,1,-1), 0,
  poly_points (82160,3), poly_offsets (20541,), poly_cells (20540,)), the deliberate exception at call 2 gives one
  "analysis_func raised" warning; v2106 exit 136 after 86 steps (85 snapshots, 28 SVDs, 85 analysis calls; the shipped
  case's divergence, as phase 3). B (module with only the hooks): FOAM FATAL "snapshot_func and svd_func must be
  callable", exit 1, both. C (one empty patch frontAndBack, 200 cells): cellPolygons=200, poly_points (800,3),
  poly_offsets (201,), poly_cells (200,), 10 steps, End, finalized, both versions. Same as phase 3 (25089082/83).
3D slice, no model, at the observer tip (tree 7ef9588; F/jobs/slice3d*.{sbatch,sh}; case3d of job 24929629, start
serial3d/0.10075 U/p/phi, POD_SLICE_Z 0.00396875 (z3), 300 steps of 5e-6 s, LLM_ENABLED=0, describe v2, async,
LLM_ANALYSIS_STEP 50 / EVERY 50, validation module as pod_svd.py):
- v2212, job 25090339: build + validation PASS; "POD plane slice: z=0.00396875 ... cut cells=20540";
  "POD mesh geometry passed to Python: cells=164320 solutionD=(1 1 1) cellPolygons=20540 ranks=1 slice z=0.00396875";
  exit 0, 300 Time lines, 300 snapshots, 6 SVDs, 300 analysis calls, End, Python finalized, 0 tracebacks; frames at
  steps 50-300 (6), each U.png, p.png, fields.npz, readable-metadata.json; max Courant 0.334753167581. Against r2
  slice-3d phase 1 z3 (job 25080032, bf7a06e, same image): 6/6 frames byte-identical (both PNGs and fields.npz sha256
  equal, all arrays equal), same cut-cells line (F/slice3d/v2212-25090339/compare_phase1.json).
- 8, job 25090340: build + validation PASS; same plane-slice line (cut cells=20540) and mesh-geometry line; exit 0,
  300/300/6/300, End, finalized, 0 tracebacks; 6 frames with the same four files; max Courant 0.334763931608;
  against the v2212 frames, mesh_cells equal and U differs by up to 1.2 (step 50) to 3.8 m/s (step 300), p by 17-54
  m²/s² (OpenFOAM 8's relaxationFactors reading; recorded only).
Unit tests (not in my list, run because the tests changed): job 25090341 (7ef9588) and 25090480 (24e9df6), unloaded,
4 cpus: ci-py310 (3.10.22) Ran 85 tests OK (78.955 s / 78.344 s); ci-py312 (3.12.15) Ran 85 OK (78.519 s / 78.407 s).

## Jobs (all mine, all COMPLETED)
25090304-07 siblings; 25090315-19 pod_account; 25090326-29 builds+validation; 25090330 Docker; 25090332-35
scenarios; 25090337-38 smoke; 25090339-40 3D slice; 25090341 unit; 25090471 run.sh failure paths; 25090475-78
builds+validation (new llm/hpc/obs); 25090479 Docker (24e9df6); 25090480 unit; 25090481-82 smoke (24e9df6).
Requeued by Slurm ("user env retrieval failed"): 25090306 and 25090317 once each (ran by themselves), 25090332 three
times (I released it once with scontrol release). No other job touched.

## Not done
- Observer-side checks of E9 are not in this task: test_async 8x50 under load, E2B quick start on v2106, 12B GPU suite
  and the 2-rank request. Only unloaded unit tests ran (85/85 on both Pythons).
- Scenarios, schedule, extra and the 3D slice ran on 7ef9588, not rerun on 24e9df6 (the trees differ only in
  llm_demo/README.md, which none of them reads). Builds, validation, Docker, smoke and unit tests ran on 24e9df6 too.
- No 3D slice run in parallel, no wedge mesh, no other POD_SLICE_Z than z3. No -Wall/-Wextra pass (warning count by
  grep only). No build against Python 3.12 headers.
- The pimpleFoam failure path was produced by a broken 0/p, which also breaks PODFoam; the run.sh order makes
  pimpleFoam fail first. A numpy installed with pip --user was simulated with a fake numpy package in a
  PYTHONUSERBASE site folder.
- Texts (PR bodies, e-mails), docs stage, TODO-HASH replacement, fork main / KO integration: other tasks.
- Copyright lines (2021 Argonne + 2026 Seungmin Yome + SPDX (other)) unchanged: the user's decision.

## Untouched
main 6677bac (clean), PythonFOAM-pr bf7a06e (clean), PythonFOAM-Korean 5c56995 (clean); r3/pr-fix cbd0e89,
r3/pr-observer 276ea8e, r2/instability 6d38337, pr/podfoam-observer bf7a06e, pr/podfoam-solver 7484d11 unchanged.

## Full commit messages (r4/pr-observer, oldest first; the first 7 are r4/pr-fix)

#### 5b3e5a32188c399e850c3e177547efcd85c04c75 (tree e469c24)

```
PODFoam: NumPy owns each snapshot; calls into Python are checked

The snapshot handed to snapshot_func was a view of a C++ buffer that the next
step overwrites; the shipped module keeps the first snapshot of each window
that way and reads the second step's values twice. Each snapshot is now an
array NumPy owns, filled from U after a finite check of U and p. A failed
import, missing function, exception or SystemExit stops the run with the
traceback. svd_func must return float64 modes, shape (3*cells, 1 or more),
finite, the same count on all ranks. For a user: mode files are dimensionless
zeroGradient fields; podTruncation (controlDict, default 5) caps the modes
written, and more columns give one warning; the case folder comes first on
sys.path; Py_FinalizeEx at exit waits for non-daemon threads; a changed cell
count stops the run; a write step with no snapshot since the last SVD now
collects one (the earlier code ran svd_func at every write step).

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### d686a64dbec54a7cf82dc3852c406775a9144adc (tree e117ab7)

```
PODFoam_Debug, APMOSFoam, AEFoam: NumPy owns each snapshot too

The three solvers pass PyArray_SimpleNewFromData over the reused C++ buffer
input_vals, so a view the module keeps reads the next step's values (their
shipped modules keep the first snapshot of each window that way, and the first
two snapshot columns, rows for AEFoam, come out equal). PyArray_SimpleNew plus
a copy of the buffer gives Python an owning array; a failed allocation stops
the run with a message. Nothing else in the three solvers changes.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### aaf80a66fd6c9eeac7d309f8d513f8685f4d0275 (tree 49403a6)

```
PODFoam: setRootCaseLists.H; floating-point traps off around Python

setRootCaseLists.H replaces the hand-written argList, so PODFoam parses its
arguments like pimpleFoam and gets the same signal handlers, including the
floating-point traps that the earlier argList(..., initialise=false) skipped.
NumPy's import overflows on purpose while probing machine limits, so the traps
are off around initialization, every call into Python and finalization:
PythonCompat.H gives sigFpe::ignore on openfoam.com and a small class on
openfoam.org, which has none; pending flags are cleared before the traps return.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### d01af1ab303d7b01fd5d134e5dc34601e7f75ad7 (tree e76d557)

```
PODFoam: optional podSvdInterval in controlDict

At its default of 0 nothing changes: a write step runs the SVD if snapshots
have been collected since the last SVD, and collects one otherwise. Above 0,
every step collects a snapshot and the SVD runs every podSvdInterval
snapshots, also on steps that write nothing else, which then hold only the
POD fields. A negative value stops the run with a message. Each step now
prints a Time = line with its deltaT; the timing lines stay.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### a7501b1ff420aed940995ba5db579b5d51264b52 (tree 46cc275)

```
pEqn: on openfoam.com select pFinal only on the final corrector

On openfoam.com a plain pEqn.solve() takes the pFinal solver throughout the
last outer iteration; with nOuterCorrectors 1, as in Run_Case, that is every
pressure corrector. pimpleFoam there solves with
mesh.solver(p.select(pimple.finalInnerIter())), the p solver until the final
corrector and pFinal there, and PODFoam now makes the same call, so its U and p
agree with pimpleFoam's on v2012, v2106 and v2212. On openfoam.org the call
stays plain, as in pimpleFoam there, and OpenFOAM 8 results do not change.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 8376b00d9706b6b0f5a1e959ac7c8ef82800f74e (tree 1476ca1)

```
PODFoam: bridge validation

validation/run.sh builds PODFoam into a fresh directory under validation/runs/
and runs ten steps of a stabilised copy of Run_Case with pimpleFoam and with
PODFoam, where a minimal python_module.py keeps the ten snapshots and returns
five SVD modes per component. verify.py checks the snapshots against the
written U, the returned modes against the written fields, and U and p against
pimpleFoam. A failed step names its log. The README lists what a module must
provide and what changes in PODFoam with the commits before this one.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 8954b2544d0f669d0079f6138eec6983944cf4d5 (tree e2dd9e2)

```
README: PODFoam snapshot fix and validation

The four solvers this series touches build on v2012, v2106, v2212 and 8, and
the README says so without widening the list for the other examples. Under
PODFoam in Contents, a pointer names the validation, what a module must provide
and the versions it passes on. The prep_env.sh sentence says its source line
must point at the bashrc of the OpenFOAM version in use, and the requirements
are given per solver: the solvers need Python 3 with numpy and their headers,
the shipped modules also matplotlib, and mpi4py or tensorflow.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 371adbab9c8b006069a92c9501431a187c4cc207 (tree ce40f50)

```
PODFoam: optional analysis_func and mesh_func hooks

A python_module.py may define two more functions. mesh_func runs once before
the first step with copies of the cell centres, volumes, solution directions
and one polygon per cell (a face of the first empty patch, or a plane slice of
a 3D mesh). analysis_func runs after every step with the time index, snapshot
count, residuals, Courant and continuity numbers and copies of U and p. They
change neither U nor p; with analysis_func the POD step collects a snapshot at
every step. In parallel the master alone calls them. HOOKS.md has the contract.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### e05643e3dbec0c3f70eddcf22a8b885e97faf4e3 (tree 84dcac8)

```
PODFoam llm_demo: an observer asking a local vision-language model

python_module.py is an example module for the two hooks. At chosen steps it
draws |U| and p, asks a vision-language model served by a local llama-server
about them, and records the answer with the arrays; model output never goes
back into the solver. Each request runs in a forked worker with a deadline, so
a slow or dead server cannot hold the solver past it. run_demo.sh runs five
synchronous or five asynchronous cases against a resident server; verify_demo.py
and verify_async.py check that the written fields equal those of the run with
no request. The unit tests need neither a solver nor a model.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 6e41943cffab1008480546e0b5c8d7195dceefe4 (tree 7d017e8)

```
PODFoam llm_demo/hpc: the GPU path

These scripts run the asynchronous suite with Gemma 4 12B on a Slurm GPU node.
setup_12b.sh fetches the pinned weights and llama.cpp and checks their SHA-256,
build_llama_cuda.sh builds llama.cpp where the prebuilt binaries need a newer
glibc, start_server.sh and stop_server.sh run the server and check that the pid
they handle is a llama-server, and async_v2.slurm runs the suite with OpenFOAM
in an Apptainer image. Everything specific to a site comes from the environment.
The runtime lives beside the repository and the job output under llm_demo/,
which its .gitignore covers.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

#### 24e9df6f5640594e2dbbd9a817231717fe8310ef (tree 251f965)

```
README: PODFoam hooks and the observer example

Under PODFoam in Contents, after the validation pointer, one line names
HOOKS.md with the two optional functions, which change neither U nor p (with
analysis_func the POD step collects a snapshot at every step), and llm_demo/,
the example module that asks a local vision-language model about the running
solver.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
```

