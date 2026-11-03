# Instability test, second round: the stated times removed (design, 2026-11-01)

Written before any request was built or sent. Work folder:
`/cluster/medbow/gscratch/syome/github_repos/pod-versions-20261030/r2/instability/`
(code in `wt/`, a worktree of `PythonFOAM` on branch `r2/instability` from `6677bac`).

## The flaw being removed

In the set of 2026-10-28 (`docs/evidence/2026-10-28-instability/`), every request
states each frame's step and time three times: in the JSON note (`step`, `time_s`),
in the caption before each picture ("Time k: step S, t = T s") and in the picture
title ("..., step S, t = T s"). The crashed runs' frames are 2e-5 to 1.2e-4 s apart,
the ended runs' frames 2e-4 to 2e-3 s apart, so the stated time between frames
alone separates the two classes (54 of 54; `independent-recount.json: frame_spacing`).

## What changes

1. **No times anywhere.** The note gives only `time: 1, 2, 3` and the image numbers;
   the captions say "Time k. Image n: ..."; the picture title has no step and no
   time. The step and time are also left out of the PNG metadata. The system prompt
   (`stability_request.STABILITY_V2OWN_SYSTEM_PROMPT`) is unchanged, byte for byte.
   Every state is drawn once and reused by every triple that has it, as before.
2. **Equal spacing in both classes (set A).** Frames of every triple are 2e-3 s apart
   in physical time, in both classes. 2e-3 s is the smallest spacing that every
   ended run's written states allow (upwind-dt2e-5 writes every 2e-4 s, upwind-dt4e-5
   every 4e-4 s, central-dt5e-6 every 2.5e-4 s, developed every 1e-3 s) and that
   a crashed run can supply: central-dt2e-5 (Δt 2e-5 s, every step written, crash
   in step 467) gives triples at run steps (last-200, last-100, last). central-dt3e-5
   (26 states, 7.8e-4 s of run) and central-dt4e-5 (9 states, 3.6e-4 s) cannot give
   a triple 4e-3 s long and are left out of set A.
3. **Text identical across items.** At build time the text parts of every request in
   a set are compared: they must be byte-identical for all items of the set. Then no
   text can carry class information; only the pictures differ. The check's result
   goes into the manifest.

## Sets

| Set | Triples | Times in text | Items (scored unstable / early unstable / stable) |
|---|---|---|---|
| `instability-eq2ms-notime` (A0) | new, 2e-3 s apart | none | 10 / 10 / 10 |
| `instability-eq2ms-reltime` (A1) | the same as A0 | "t - t1 = 0, 0.002, 0.004 s" in note and captions, the same string in every item | 10 / 10 / 10 |
| `instability-oct28-notime` (B0) | the 70 triples of 2026-10-28, same run steps | none | 27 / 16 / 27 |

- A0 scored unstable: central-dt2e-5, last frame 1 to 10 steps before the crash
  (run steps 457 to 466), frames at last-200, last-100, last. Early (not scored):
  last frame 12, 15, 20, 30, 50, 75, 100, 150, 200, 260 steps before the crash.
- A0 stable (10): upwind-dt2e-5 2 (gap 10 written states), upwind-dt4e-5 2 (gap 5),
  central-dt5e-6 3 (gap 8), developed 3 (gap 2, states from t = 0.032 s on). Each
  triple ends at least 100 run steps before the run's last step; the usable starts
  of a run are cut into equal parts and one start is drawn in each (seed 20261101),
  as `instability_test.stable_triples` does.
- A1 shows whether stating the (equal) spacing changes the answers; it isolates the
  text's effect on the fair set. The images of A0 and A1 are the same files.
- B0 shows the effect of removing the times from the old set, item by item against
  the 2026-10-28 answers of the same two models (same triples, same prompt, same
  server settings; the only change is the text and the picture titles).
- Labels and the balanced score as on 2026-10-28: a run that crashed (sigFpe trace,
  no End) is unstable; its triples ending 1 to 10 steps before the crash are scored;
  ended runs give stable triples. Fixed answer: half.

## Models and settings

Gemma 4 12B QAT Q4_0 and Gemma 4 31B QAT Q4_0 (files present in
`PythonFOAM/llm-runtime-12b/`, hashes in `hpc/models.tsv`), llama.cpp b11429 CUDA,
all layers on the GPU, context 4096, batch 512, ubatch 512, image token limit 256,
parallel 1, temperature 0, seed 20261021, max_tokens 320, no prompt cache: the
settings of job 24929533. One GPU job runs 12B then 31B on all three sets
(130 requests each). No new download. 26B-A4B and Qwen are not run.

## Scoring (per set, per model, and for the array rules)

- Right of scored items; flagged (`unstable`) of scored triples ending before a
  crash; flagged of normal (stable) triples; `cannot_tell`.
- Rules from the arrays as on 2026-10-28: peak |U| in the window, last over first
  frame, above 1.05, 1.1, 1.2, 1.5, 2.0; largest cell-to-cell |U| jump, last over
  first, above 1.2, 1.5, 2.0, 3.0; the best single threshold on these items
  (optimistic bound).
- How early `unstable` is said (by steps from the last frame to the crash), by run.
- For B0: the number of items whose answer changed against the 2026-10-28 run of
  the same model, and in which direction.

## What stays unfair or weak, known before the run

1. The pictures still show how much the flow changed between frames. In set A this
   is equalised (2e-3 s in both classes); in B0 it is not (crashed-run frames
   2e-5 to 1.2e-4 s apart, ended-run frames 2e-4 to 2e-3 s), so B0 removes only
   the text leak.
2. In set A every unstable item comes from one run (central-dt2e-5) and the ten
   scored triples share frames (last frames 457 to 466, middles 357 to 366, firsts
   257 to 266): they are ten answers about one event, not ten independent cases.
   The stable items come from four runs.
3. Scheme look: central differencing leaves cell-scale wiggles in the pictures and
   the upwind runs are smooth. The stable class holds the central run with a small
   time step (3 of 10 in A, 6 of 27 in B0) to counter this, not fully.
4. Absolute values: the crashed run's peak |U| in the window (39 to 97 m/s before the
   blow-up) is above the stable runs' typical 36 to 45 m/s in the last frames of the
   scored triples. A model reading only the colour-bar maximum can use that, and
   so can the rules. That is a property of this flow, reported with the numbers.
5. The developed run's frames (t = 0.032 to 0.1 s) show a flow still developing from
   rest; all other frames are at t ≥ 0.1 s.
6. The best thresholds are chosen on the same items.
7. In set A the span of a triple is 400 run steps, so the rules' ratios cover the
   whole last 400 steps of the run; on 2026-10-28 the crashed triples spanned 2 to
   6 steps. The rule numbers of the two sets are therefore not comparable.
8. Twenty scored items in set A: one answer moves the score by 5 %.

## Jobs planned

1. CPU: build the three sets (draw about 250 states, two pictures each), check them,
   run the text-identity check. Partition teton,non-investor,wildiris,mb, 4 CPUs,
   16 GB, 1 h.
2. GPU: non-investor-gpu, 1 GPU (l40s|a6000; A30 24 GB left out: the 31B file is
   17 GB plus the projector and a 4096 context), 8 CPUs, 48 GB, 1 h 30.
3. Report and recount on the login node (seconds).
